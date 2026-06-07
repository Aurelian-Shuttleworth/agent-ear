# Transcribe a Meeting with Speaker Labels

> **Goal**: Transcribe a multi-speaker meeting with speaker labels, action items, and notable quotes.

## Prerequisites

- `agent-ear` installed (see [README](../../README.md))
- Authentication configured — either [Google AI Studio](setup-google-ai-studio.md) or [Vertex AI](setup-vertex-ai.md)
- Working microphone (built-in or external)

## Steps

### 1. Launch interactive mode and select Meeting

Run `agent-ear` without the `--auto` flag to start the interactive TUI:

```bash
agent-ear
```

From the mode selection menu, choose:

```
🤝 Record Meeting — Multi-speaker, action points & quotes
```

<!-- REVIEW: Verify the exact emoji + wording still matches select_mode() if the menu changes -->

> [!TIP] 📸 **Screenshot candidate**
> A screenshot of the Gum meeting mode selection menu would help readers identify the correct option quickly. Worth adding?

### 2. Choose how speakers are identified

Agent-ear asks how to label speakers in the transcript. Pick one:

| Option | When to use | Transcript labels |
|:-------|:------------|:------------------|
| **👤 By name** | You know who's in the room | `Alice:`, `Bob:`, etc. |
| **🔢 By number** | Ad-hoc meeting, unknown attendees | `Person 1:`, `Person 2:`, etc. |

If you choose **By name**, enter a comma-separated list of participants when prompted:

```
Alice, Bob, Charlie
```

If a speaker can't be distinguished, the transcript falls back to `Unknown Speaker`.

### 3. Configure and record

After speaker setup, agent-ear walks you through the standard configuration:

1. **Output format** — `markdown`, `json`, or `raw`
2. **Transcription model** — Flash-Lite (fast/cheap), Flash (balanced), or Pro (premium)
3. **Output directory** — where the transcript file is saved
4. **Topic slug** — optional; auto-generated if left blank

Review the summary screen, then confirm to start recording. Speak naturally — agent-ear captures audio until you stop (press `Ctrl+C` or the designated stop key).

> [!TIP] 🎬 **Terminal recording candidate**
> A terminal recording (e.g. `vhs` or `asciinema`) showing the full meeting flow — from mode selection through recording — would be a valuable addition here.

### 4. Understand the output structure

The meeting transcript is written as a Markdown file with three sections:

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

## For agents (`--auto` mode)

<!-- REVIEW: This section is the primary value for agentic consumers — keep the prompt template in sync with collect_meeting_setup() -->

Agents can replicate the meeting workflow entirely via `--auto` by passing the meeting prompt with `--prompt`. No interactive TUI is needed.

> [!NOTE] 🔍 **Context for reviewer**
> The meeting prompt template below is the system instruction that the LLM receives. It constrains the transcription model's output format — enforcing speaker labels, action-item checkboxes, and blockquote-formatted notable quotes. The model has no meeting-specific logic of its own; all structure comes from this prompt.

### With named speakers

```bash
agent-ear --auto \
  --prompt 'You are transcribing a multi-speaker meeting.

<instructions>
1. SPEAKER IDENTIFICATION: Identify each speaker by their name: Alice, Bob, Charlie. If you cannot distinguish a speaker, label them as '\''Unknown Speaker'\''.
2. TRANSCRIPTION: Provide a full, accurate transcription with speaker labels.
3. ACTION ITEMS: After the transcription, list all action items mentioned.
   Format each as: '\''- [ ] [Owner]: [Action item description]'\''
4. NOTABLE QUOTES: Extract 3-5 notable, impactful, or decision-defining quotes.
   Format each as: '\''> "[Quote]" — [Speaker]'\''
</instructions>

<output_structure>
## Meeting Transcription

[Full speaker-labeled transcription here]

## Action Items

- [ ] [Owner]: [Description]

## Notable Quotes

> "[Quote]" — [Speaker]
</output_structure>

Stay grounded in the audio. Do not infer action items or quotes that were not explicitly spoken.' \
  --output-format markdown \
  --output-dir ./meetings/
```

### With numbered speakers

Replace the speaker identification line:

```bash
--prompt '...
1. SPEAKER IDENTIFICATION: Label speakers as Person 1, Person 2, Person 3, etc. based on distinct voices.
...'
```

Everything else in the prompt template stays the same.

### Prompt template reference

For convenience, here is the full prompt template with a placeholder for the speaker instruction:

```text
You are transcribing a multi-speaker meeting.

<instructions>
1. SPEAKER IDENTIFICATION: {{SPEAKER_INSTRUCTION}}
2. TRANSCRIPTION: Provide a full, accurate transcription with speaker labels.
3. ACTION ITEMS: After the transcription, list all action items mentioned.
   Format each as: '- [ ] [Owner]: [Action item description]'
4. NOTABLE QUOTES: Extract 3-5 notable, impactful, or decision-defining quotes.
   Format each as: '> "[Quote]" — [Speaker]'
</instructions>

<output_structure>
## Meeting Transcription

[Full speaker-labeled transcription here]

## Action Items

- [ ] [Owner]: [Description]

## Notable Quotes

> "[Quote]" — [Speaker]
</output_structure>

Stay grounded in the audio. Do not infer action items or quotes that were not explicitly spoken.
```

Where `{{SPEAKER_INSTRUCTION}}` is one of:

- **Named**: `Identify each speaker by their name: Alice, Bob, Charlie. If you cannot distinguish a speaker, label them as 'Unknown Speaker'.`
- **Numbered**: `Label speakers as Person 1, Person 2, Person 3, etc. based on distinct voices.`

## Tips

- **Quiet environment** — background noise degrades speaker separation. Close windows and mute notifications.
- **Single microphone** — one shared mic (e.g. a conference mic in the centre of the table) works better than multiple individual mics. The model distinguishes speakers by voice characteristics, not by input channel.
- **Speaker pauses** — brief pauses between speakers help the model identify transitions. Avoid talking over each other when possible.
- **Use named speakers** — named identification produces more useful transcripts, especially for action items. The model can confidently assign owners to tasks when it knows who's who.
- **Review action items** — the model extracts action items grounded in the audio, but always review the list for completeness. Implicit commitments may be missed if they weren't stated explicitly.
