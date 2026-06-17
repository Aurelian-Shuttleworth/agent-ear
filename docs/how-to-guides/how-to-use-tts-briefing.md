# How to Brief Users with Spoken Instructions

## Prerequisites

- `agent-ear` installed (see [README](../../README.md))
- Authentication configured: either [Google AI Studio](how-to-setup-google-ai-studio.md) or [Vertex AI](how-to-setup-vertex-ai.md)
- Working audio output (speakers or headphones)

## Steps

### 1. Create a briefing file

Write the text you want agent-ear to speak aloud. This is what the user will hear before the microphone activates.

```markdown
<!-- briefing.md -->
Hello! I need you to describe the current status of the project.
Please cover what's been completed, any blockers you're facing,
and your priorities for the rest of the week.
Take your time — there's no rush.
```

### 2. Create a prompt file

Write the transcription constraints that guide how the recording is processed.

```markdown
<!-- prompt.md -->
Transcribe this project status update. Structure the output as:
- **Completed**: Items finished since last update
- **Blockers**: Issues preventing progress
- **Priorities**: Focus areas for the remaining week

Use bullet points. Preserve the speaker's meaning but clean up filler words.
```

### 3. Run with briefing and prompt

```bash
agent-ear --non-interactive \
  --prompt-file prompt.md \
  --briefing-file briefing.md
```

The flow is:

1. 🎙️ **TTS speaks** the briefing text aloud
2. ⏳ Brief pause for the user to prepare
3. 🔴 **Recording starts**: microphone captures the response
4. 📝 **Transcription runs** using the prompt constraints

### 4. Control prosody with Director's Notes

Add YAML frontmatter to the briefing file to control voice style:

```markdown
---
style: calm, professional
pace: slowly
voice: Kore
---
Hello! I need you to describe the current status of the project.
Please cover what's been completed, any blockers you're facing,
and your priorities for the rest of the week.
```

#### Supported frontmatter fields

| Field | Purpose | Default | Example |
|:------|:--------|:--------|:--------|
| `style` | Tone and delivery style (controls TTS prosody) | `warm and natural` | `calm, professional` |
| `pace` | Documents intended pacing (for human reference) | — | `slowly` |
| `voice` | Gemini TTS voice name | `Kore` | `Puck`, `Charon`, `Kore` |
| `language_code` | BCP-47 language code | `en-US` | `en-GB`, `nl-NL` |

#### How Director's Notes work

The TTS prompt is constructed as a **style prefix** separated by a colon from the spoken text:

```
Say the following in a calm, professional tone: Hello! I need you to...
```

Everything before the colon is a stage direction (never spoken). 

### 5. Model and auth

TTS uses the `gemini-2.5-flash-tts` model with the same authentication as main transcription, no additional setup is required. If you have either an AI Studio key or Vertex AI credentials configured, TTS works automatically.

## Example: agent-driven voice capture

A common pattern for AI agents calling agent-ear:

```bash
# Agent writes context-specific briefing
cat > /tmp/briefing.md << 'EOF'
---
style: warm, encouraging
voice: Kore
---
Hi! I've reviewed the pull request and have a few questions.
Could you walk me through the design decisions behind the new caching layer?
Specifically, why you chose an LRU strategy over TTL-based expiration.
EOF

# Agent writes structured transcription prompt
cat > /tmp/prompt.md << 'EOF'
Transcribe this technical explanation. Extract:
- Design rationale for LRU cache
- Trade-offs considered
- Any follow-up decisions mentioned

Format as structured notes with headers.
EOF

# Agent runs the capture
agent-ear --non-interactive \
  --prompt-file /tmp/prompt.md \
  --briefing-file /tmp/briefing.md \
  --output-dir ./notes/ \
  --output-format markdown
```
