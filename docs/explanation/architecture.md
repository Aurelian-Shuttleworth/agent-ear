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
    Studio --> Limited["Most features<br/>Files API ≤2 GB<br/>GCS uploads ❌"]

    style Vertex fill:#22c55e,stroke:#16a34a,color:#fff
    style Studio fill:#eab308,stroke:#ca8a04,color:#000
    style Fail fill:#ef4444,stroke:#dc2626,color:#fff
```

### Why two auth paths?

The honest answer: **onboarding friction kills tools.**

Vertex AI is the "right" answer for production — it gives you GCS uploads for large files, project-scoped billing, and enterprise features. But setting it up requires a GCP project, enabled APIs, and Application Default Credentials. That's a 5-minute setup that filters out 90% of people who just want to try the tool.

Google AI Studio needs one API key and zero infrastructure. You paste it, export it, and you're running in 60 seconds. The tradeoff is no GCS support — but AI Studio can still handle files up to 2 GB via the Gemini Files API. Only files exceeding 2 GB require Vertex AI with GCS staging.

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
    participant Judge as Gemini (flash)
    participant Mic as Microphone
    participant Trans as Gemini (transcription)

    Agent->>Ear: --prompt-file requirements.txt --auto
    Ear->>Judge: "Evaluate this transcription prompt"
    Judge-->>Ear: {score: 4, valid: true, thinking_level: "medium", extra_tokens: 2048}
    Note over Ear: ✅ Score ≥ 3 → proceed<br/>Apply thinking hints
    Ear->>Mic: 🎙️ Start recording
    Mic-->>Ear: audio.wav
    Ear->>Trans: audio + system_instruction<br/>+ thinking_config + adjusted token budget
    Trans-->>Ear: Structured transcription
    Ear-->>Agent: {output_path, content, cost}
```

### Why validate before recording?

Imagine this: an AI agent constructs a vague prompt like _"process the audio"_, the human speaks for 10 minutes, and the transcription comes back as an unusable blob. The human's time is wasted, and the agent has to retry.

Prompt validation catches this _before_ any recording happens. A separate Gemini call (using `gemini-3.5-flash`) scores the prompt on five criteria:

1. **Instruction clarity** — does it specify what to extract?
2. **Output structure** — does it define the expected format?
3. **Grounding** — does it require references to the actual audio?
4. **Negative constraints** — does it say what to avoid?
5. **Completeness** — does it handle edge cases?

If the score is below 3/5, the pipeline exits with code `2` and returns an improved prompt suggestion. The agent can refine and retry without ever bothering the human.

Beyond scoring, the validator also emits **transcription hints** — a `thinking_level` recommendation (`low`, `medium`, or `high`) and an `extra_tokens` budget adjustment (0–16384). These hints configure the downstream transcription model's reasoning effort and output token budget, optimising quality for complex prompts without manual tuning.

> [!NOTE]
> Validation is deliberately **fail-open**: if the validation call itself errors (network issue, quota), the pipeline proceeds anyway. The goal is to catch bad prompts, not block good ones.

The same pattern applies to TTS briefings — a two-layer check (static regex checks for free, then LLM-as-a-judge) catches non-speakable content like markdown headers, URLs, and pacing mismatches before the TTS API is called.

## Media Upload Strategy

```mermaid
flowchart TD
    Upload["upload_media()"] --> Explicit{"--gcs-bucket<br/>provided?"}
    Explicit -->|"Yes"| GCS["📤 GCS upload<br/>Part.from_uri()"]
    Explicit -->|"No"| SizeCheck{"File size<br/>≤ 100 MB?"}
    SizeCheck -->|"Yes"| Inline["📤 Inline upload<br/>Part.from_bytes()"]
    SizeCheck -->|"No"| BackendCheck{"Auth<br/>backend?"}
    BackendCheck -->|"Vertex AI"| GCSAuto["📤 GCS upload<br/>(auto-derived bucket)"]
    BackendCheck -->|"AI Studio"| FilesCheck{"File size<br/>≤ 2 GB?"}
    FilesCheck -->|"Yes"| FilesAPI["📤 Gemini Files API<br/>client.files.upload()<br/>(48h storage, async polling)"]
    FilesCheck -->|"No"| Error["❌ File too large<br/>Use --gcs-bucket"]

    style Inline fill:#22c55e,stroke:#16a34a,color:#fff
    style GCS fill:#0ea5e9,stroke:#0284c7,color:#fff
    style GCSAuto fill:#0ea5e9,stroke:#0284c7,color:#fff
    style FilesAPI fill:#a855f7,stroke:#9333ea,color:#fff
    style Error fill:#ef4444,stroke:#dc2626,color:#fff
```

### The 100 MB threshold

The Gemini API accepts inline uploads up to 100 MB. That comfortably covers most voice recordings and short videos. For anything larger, agent-ear routes through one of two backends:

- **Vertex AI users** → GCS staging. The file is uploaded to a Google Cloud Storage bucket and a `gs://` URI is passed to Gemini.
- **AI Studio users** → Gemini Files API. The file is uploaded to Google's servers via `client.files.upload()`, stored for 48 hours at no cost, and referenced by file name. This supports files up to 2 GB.

If `--gcs-bucket` is explicitly provided (via flag or `AGENT_EAR_GCS_BUCKET` env var), GCS is used regardless of file size or auth backend.

### Bucket must pre-exist

Unlike earlier versions, agent-ear no longer auto-provisions GCS buckets. If a GCS upload is needed and the bucket doesn't exist, the Google Cloud Storage client raises a `NotFound` error with a clear message. This is intentional — agents shouldn't silently create cloud resources that cost money.

See the [GCS staging guide](../guides/setup-gcs-staging.md) for manual bucket creation instructions.

### Why 7-day lifecycle?

Staging files are only needed for the duration of a single Gemini API call — a few minutes at most. A 7-day lifecycle rule is generous enough to survive retries and debugging, but short enough that forgotten files don't accumulate costs. At Google Cloud Storage pricing (~$0.02/GB/month), even leaving files for 7 days costs effectively nothing.

## Cost Tracking

Every Gemini API call in the pipeline is tracked through a `CostTracker` that threads through all phases:

```mermaid
flowchart LR
    V["Prompt Validation<br/>flash"] --> B["Briefing Validation<br/>flash"]
    B --> T["Transcription<br/>flash / flash-lite / pro"]
    T --> O["Obsidian Final Pass<br/>flash"]

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

For current per-model pricing, see the [Google AI pricing page](https://ai.google.dev/pricing) and [Vertex AI pricing page](https://cloud.google.com/vertex-ai/generative-ai/pricing).

### Per-call reporting

At the end of a pipeline run, you see:

```
💰 gemini-3.5-flash: $0.0001 (in: 1,024, out: 256, think: 64)
💰 gemini-3.5-flash: $0.0003 (in: 18,432, out: 512, think: 128)
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
- **Dynamic token budgets** — output token limits scale with recording duration (~200 tokens per minute of speech, floor 8192, cap 65536). Video defaults to 32768. The prompt validator can add up to 16384 extra tokens via its `extra_tokens` hint.
- **Validator-driven reasoning** — the prompt validator emits `thinking_level` and `extra_tokens` hints that configure the transcription model's reasoning depth and token budget, optimising quality without manual tuning.
