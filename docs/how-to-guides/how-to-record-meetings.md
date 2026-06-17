
# Transcribe a Meeting with Speaker Labels

This how-to guide shows you how to use interactive mode to record, transcribe and contextualize meetings with agent ear.

## Prerequisites

- `agent-ear` installed (see [README](../../README.md))
- Authentication configured — either [Google AI Studio](how-to-setup-google-ai-studio.md) or [Vertex AI](how-to-setup-vertex-ai.md)
- Working microphone (built-in or external)

## Steps

### 1. Launch interactive mode and select Templates --> Meeting notes

Run `agent-ear` without the `--non-interactive` flag to start the interactive TUI:

```bash
agent-ear
```

From the mode selection menu, choose:

```
📋 Templates ▸ — Choose a premade prompt template
```

Then choose:

```
🤝 Record Meeting
```
### 2. Configure and record

Choose your preferred output format, transcription model and output directory (see also: how-to-use-interactive-mode.md). Then confirm to start recording. Speak naturally: `agent-ear` captures audio until you stop (press `Ctrl+C` or the designated stop key).

> [!NOTE]
> **Automatic Recovery**: If the transcription fails (e.g., due to a lost internet connection or API error), your raw audio is safely preserved in the `.recovery/` directory so it can be retrieved or processed later.

### 3. Understand the output structure

Agent-ear's output is written as a Markdown file with three sections:

```markdown
## Meeting Transcription

Alice: I think we should ship the v2 API this week.
Bob: Agreed, but we need to finalize the auth middleware first.
Alice: Right — Charlie, can you handle the token refresh logic?
Charlie: Yes, I'll have a PR up by Thursday.

## Action Items

- [ ] Charlie: Implement token refresh logic and open PR by Thursday
- [ ] Bob: Finalize auth middleware before v2 API ship

## Notable Quotes

> "I think we should ship the v2 API this week." — Alice
> "I'll have a PR up by Thursday." — Charlie
```

- **Meeting Transcription** — full speaker-labeled transcript, preserving conversation flow
- **Action Items** — every commitment or task mentioned, as a checkbox list with an owner
- **Notable Quotes** — 3–5 impactful or decision-defining quotes from the discussion

Speakers are differentiated by the AI agent by the sound of their voice. If a speaker can't be distinguished, the transcript falls back to `Unknown Speaker` or numbered speakers (speaker 1, speaker 2, etc.).

## For agents (`--non-interactive` mode)

Agents can replicate the meeting workflow entirely via `--non-interactive` by passing the meeting prompt with `--prompt`. No interactive TUI is needed.

## Tips

- **Quiet environment** — background noise degrades speaker separation. Close windows and mute notifications.
- **Single microphone** — one shared mic (e.g. a conference mic in the centre of the table) works better than multiple individual mics. The model distinguishes speakers by voice characteristics, not by input channel.
- **Speaker pauses** — brief pauses between speakers help the model identify transitions. Avoid talking over each other when possible.
- **Use named speakers** — named identification produces more useful transcripts, especially for action items. The model can confidently assign owners to tasks when it knows who's who.
- **Review action items** — the model extracts action items grounded in the audio, but always review the list for completeness. Implicit commitments may be missed if they weren't stated explicitly.
