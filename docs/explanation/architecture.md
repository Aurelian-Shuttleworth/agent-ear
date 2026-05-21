# Architecture: Why Three Binaries?

agent-ear could have been a single script. Instead, it's three binaries, two auth backends, and a validation layer that calls the LLM _before_ you even start recording. This page explains why.

## The 3-Binary Design

```mermaid
graph TD
    A["agent-ear<br/>(dispatcher)"] -->|"--auto flag<br/>or non-TTY stdin"| B["agent-ear-core<br/>(Python pipeline)"]
    A -->|"interactive TTY<br/>no --auto flag"| C["agent-ear-interactive<br/>(Gum TUI wizard)"]
    C -->|"exec agent-ear-core --auto"| B

    style A fill:#6366f1,stroke:#4f46e5,color:#fff
    style B fill:#0ea5e9,stroke:#0284c7,color:#fff
    style C fill:#8b5cf6,stroke:#7c3aed,color:#fff
```

| Binary | Language | Purpose |
|:-------|:---------|:--------|
| `agent-ear` | Bash | Smart dispatcher — routes based on CLI flags and TTY state |
| `agent-ear-core` | Python | The actual pipeline: validate → brief → record → transcribe |
| `agent-ear-interactive` | Bash + [Gum](https://github.com/charmbracelet/gum) | Terminal wizard with guided mode selection and config |

### Why not one binary?

Two fundamentally different consumers need different interfaces:

**AI agents** need `--auto` and structured output. They pass a system prompt, skip interactive menus, and parse the result. They don't have a TTY. The Python backend handles this natively.

**Humans** need guidance. Which mode? Which model? What's a "system prompt"? The Gum TUI wizard walks them through every decision with styled menus and confirmation screens, then delegates to `agent-ear-core --auto` with the assembled flags.

The **dispatcher** is the glue. Its routing logic is trivial:

```bash
# Any of these flags → bypass interactive, go straight to core
for arg in "$@"; do
  case "$arg" in
    --auto|--help|-h) exec agent-ear-core "$@" ;;
  esac
done

# Not a TTY (piped, cron, agent) → core
[[ ! -t 0 ]] && exec agent-ear-core "$@"

# Interactive human → TUI wizard
exec agent-ear-interactive "$@"
```

This separation means agents never see the TUI code, and humans never need to know the flag syntax. Both paths converge on the same Python pipeline.

## Auth Backend Design

```mermaid
flowchart TD
    Start["create_client()"] --> CheckProject{"Project ID<br/>available?"}
    CheckProject -->|"--project-id<br/>or GOOGLE_CLOUD_PROJECT<br/>or gcloud config"| Vertex["Vertex AI Client<br/>(ADC auth)"]
    CheckProject -->|No project| CheckKey{"GOOGLE_API_KEY<br/>set?"}
    CheckKey -->|Yes| Studio["AI Studio Client<br/>(API key)"]
    CheckKey -->|No| Fail["❌ No auth configured"]

    Vertex --> Full["Full features<br/>GCS uploads ✅<br/>All models ✅"]
    Studio --> Limited["Most features<br/>GCS uploads ❌<br/>≤20 MB files only"]

    style Vertex fill:#22c55e,stroke:#16a34a,color:#fff
    style Studio fill:#eab308,stroke:#ca8a04,color:#000
    style Fail fill:#ef4444,stroke:#dc2626,color:#fff
```

### Why two auth paths?

The honest answer: **onboarding friction kills tools.**

Vertex AI is the "right" answer for production — it gives you GCS uploads for large files, project-scoped billing, and enterprise features. But setting it up requires a GCP project, enabled APIs, and Application Default Credentials. That's a 5-minute setup that filters out 90% of people who just want to try the tool.

Google AI Studio needs one API key and zero infrastructure. You paste it, export it, and you're running in 60 seconds. The tradeoff is no GCS support, which means files must stay under 20 MB (the Gemini inline upload limit).

The resolution order is intentional:

1. **Vertex AI first** — if a project ID exists (from flag, env var, or `gcloud config`), use it. This is the "batteries included" path.
2. **AI Studio fallback** — if no project but `GOOGLE_API_KEY` is set, use it. Zero friction.
3. **Fail with clear instructions** — if neither is configured, print exactly what to do.

This means upgrading from AI Studio to Vertex AI is just setting one environment variable — no code changes, no config files.

## Prompt Validation: LLM-as-a-Judge

```mermaid
sequenceDiagram
    participant Agent as AI Agent
    participant Ear as agent-ear-core
    participant Judge as Gemini (flash-lite)
    participant Mic as Microphone
    participant Trans as Gemini (transcription)

    Agent->>Ear: --prompt-file requirements.txt --auto
    Ear->>Judge: "Evaluate this transcription prompt"
    Judge-->>Ear: {score: 4, valid: true, feedback: "..."}
    Note over Ear: ✅ Score ≥ 3 → proceed
    Ear->>Mic: 🎙️ Start recording
    Mic-->>Ear: audio.wav
    Ear->>Trans: audio + system_instruction
    Trans-->>Ear: Structured transcription
    Ear-->>Agent: {output_path, content, cost}
```

### Why validate before recording?

Imagine this: an AI agent constructs a vague prompt like _"process the audio"_, the human speaks for 10 minutes, and the transcription comes back as an unusable blob. The human's time is wasted, and the agent has to retry.

Prompt validation catches this _before_ any recording happens. A separate Gemini call (using the cheapest model, `gemini-3.1-flash-lite-preview`) scores the prompt on five criteria:

1. **Instruction clarity** — does it specify what to extract?
2. **Output structure** — does it define the expected format?
3. **Grounding** — does it require references to the actual audio?
4. **Negative constraints** — does it say what to avoid?
5. **Completeness** — does it handle edge cases?

If the score is below 3/5, the pipeline exits with code `2` and returns an improved prompt suggestion. The agent can refine and retry without ever bothering the human.

> [!NOTE]
> Validation is deliberately **fail-open**: if the validation call itself errors (network issue, quota), the pipeline proceeds anyway. The goal is to catch bad prompts, not block good ones.

The same pattern applies to TTS briefings — a two-layer check (static regex checks for free, then LLM-as-a-judge) catches non-speakable content like markdown headers, URLs, and pacing mismatches before the TTS API is called.

## GCS Staging: Why Not Always Inline?

```mermaid
flowchart TD
    Upload["_upload_media()"] --> SizeCheck{"File size<br/>≤ 20 MB?"}
    SizeCheck -->|"Yes"| Inline["📤 Inline upload<br/>Part.from_bytes()"]
    SizeCheck -->|"No"| VertexCheck{"Vertex AI<br/>mode?"}
    VertexCheck -->|"No (AI Studio)"| Error["❌ File too large<br/>Switch to Vertex AI"]
    VertexCheck -->|"Yes"| BucketCheck{"Bucket<br/>exists?"}
    BucketCheck -->|"Yes"| GCS["📤 GCS upload<br/>Part.from_uri()"]
    BucketCheck -->|"No"| AutoMode{"--auto<br/>flag?"}
    AutoMode -->|"Yes"| AutoError["❌ Bucket missing<br/>(no interactive provisioning)"]
    AutoMode -->|"No"| Provision["🔧 Interactive provisioning<br/>1. Enable Storage API<br/>2. Create bucket<br/>3. Set 7-day lifecycle"]
    Provision --> GCS

    style Inline fill:#22c55e,stroke:#16a34a,color:#fff
    style GCS fill:#0ea5e9,stroke:#0284c7,color:#fff
    style Error fill:#ef4444,stroke:#dc2626,color:#fff
    style AutoError fill:#ef4444,stroke:#dc2626,color:#fff
```

### The 20 MB problem

The Gemini API accepts inline uploads up to 20 MB. That covers most voice recordings (a 10-minute mono WAV at 44.1 kHz is about 50 MB, but shorter recordings fit), but videos easily exceed this — a 5-minute 720p MP4 is typically 30–80 MB.

For anything over 20 MB, agent-ear uploads to a Google Cloud Storage bucket and passes a `gs://` URI to Gemini instead. This requires Vertex AI mode (a GCP project with credentials).

### Auto-provisioning

First-time users hit a cold-start problem: they don't have a GCS bucket yet. The interactive provisioning flow handles this:

1. **Check the Storage API** — is `storage.googleapis.com` enabled on the project? If not, offer to enable it.
2. **Check the bucket** — does `{project}-transcribe-staging` exist? If not, offer to create it.
3. **Set lifecycle rules** — the bucket gets a 7-day auto-delete rule on all objects. Staging files are ephemeral; the transcription output is what matters.

In `--auto` mode (agent-driven), provisioning is skipped and errors are raised instead. Agents shouldn't silently create cloud resources that cost money.

### Why 7-day lifecycle?

Staging files are only needed for the duration of a single Gemini API call — a few minutes at most. A 7-day lifecycle rule is generous enough to survive retries and debugging, but short enough that forgotten files don't accumulate costs. At Google Cloud Storage pricing (~$0.02/GB/month), even leaving files for 7 days costs effectively nothing.

## Cost Tracking

Every Gemini API call in the pipeline is tracked through a `CostTracker` that threads through all phases:

```mermaid
flowchart LR
    V["Prompt Validation<br/>flash-lite"] --> B["Briefing Validation<br/>flash-lite"]
    B --> T["Transcription<br/>flash / flash-lite / pro"]
    T --> O["Obsidian Final Pass<br/>flash-lite"]

    V -.->|"track()"| CT["CostTracker"]
    B -.->|"track()"| CT
    T -.->|"track()"| CT
    O -.->|"track()"| CT

    CT --> Summary["💰 Total: $0.0042"]

    style CT fill:#f59e0b,stroke:#d97706,color:#000
```

### What gets counted

Each API response includes `usage_metadata` with four token types:

| Token type | Billing rate | Notes |
|:-----------|:-------------|:------|
| Input tokens | Standard rate | Prompt + audio/video content |
| Output tokens | Higher rate | Generated transcription |
| Thinking tokens | Output rate | Chain-of-thought (billed as output) |
| Cached tokens | Reduced rate (~10× cheaper) | Re-used context across calls |

The tracker computes a dollar estimate per call using a built-in pricing table. This isn't a bill — it's an approximation to help agents make cost-aware decisions (e.g., choosing `flash-lite` over `pro` when quality requirements are modest).

### Per-call reporting

At the end of a pipeline run, you see:

```
💰 gemini-3.1-flash-lite-preview: $0.0001 (in: 1,024, out: 256, think: 64)
💰 gemini-3.1-flash-lite-preview: $0.0003 (in: 18,432, out: 512, think: 128)
💰 Total: $0.0004
```

The first line is prompt validation; the second is transcription. For a typical voice note, the total cost is well under a cent.

## The Pipeline, End to End

Putting it all together, here's the full data flow through `agent-ear-core`:

```mermaid
flowchart TD
    subgraph "0. Config Resolution"
        CLI["CLI flags"] --> Resolve["4-tier chain:<br/>CLI → env → gcloud → default"]
        Resolve --> Auth["create_client()<br/>Vertex → AI Studio → fail"]
    end

    subgraph "1. Validation"
        Auth --> LoadPrompt["Load agent prompt<br/>(file or inline)"]
        LoadPrompt --> ValidatePrompt["🔍 Validate prompt<br/>(LLM-as-a-judge)"]
        ValidatePrompt -->|"score < 3"| Reject["❌ Exit code 2<br/>+ improved prompt"]
        ValidatePrompt -->|"score ≥ 3"| ValidateBriefing["🔍 Validate briefing<br/>(static + LLM)"]
    end

    subgraph "2. Briefing"
        ValidateBriefing --> TTS["🗣️ TTS briefing<br/>(Gemini TTS → afplay)"]
    end

    subgraph "3. Capture"
        TTS --> Record["🎙️ Record audio<br/>or load video/file"]
        Record --> Safety["🛡️ Safety copy<br/>(.recovery/)"]
    end

    subgraph "4. Transcription"
        Safety --> Upload["📤 Upload media<br/>(inline or GCS)"]
        Upload --> Transcribe["✨ Gemini transcription<br/>(system_instruction separation)"]
        Transcribe --> FinalPass["📝 Obsidian final pass<br/>(add frontmatter if missing)"]
    end

    subgraph "5. Output"
        FinalPass --> Save["💾 Save .md / .json / .txt"]
        Save --> Cost["💰 Cost summary"]
        Cost --> Cleanup["🧹 Cleanup<br/>(remove temp + recovery files)"]
    end

    style Reject fill:#ef4444,stroke:#dc2626,color:#fff
```

Key design decisions visible in this flow:

- **System instruction separation** — the agent's prompt goes in `system_instruction`, not mixed with the audio content. This follows Gemini best practices for constrained generation.
- **Safety copy before transcription** — recordings are backed up to `.recovery/` immediately after capture, before any API call. If transcription crashes, the recording survives.
- **Cleanup only on success** — temp files and recovery copies are only deleted after the output is saved. Partial failures preserve everything.
- **Dynamic token budgets** — for audio over 2 minutes, the output token limit scales with recording duration (~200 tokens per minute of speech), preventing truncation of long recordings.
