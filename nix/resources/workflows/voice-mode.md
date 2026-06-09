---
description: Enter voice interaction mode — listen, execute, and respond via TTS in a loop.
---

> **Skills Used:** `@agent-ear`, `@agent-ear-capture`, `@agent-ear-briefing`

1. **Listen**: Record the user's voice request
   - `agent-ear --non-interactive --output-format json`
   - Parse the JSON output: `{ "date": "...", "slug": "...", "content": "..." }`
   - If exit code ≠ 0 → report error and retry

2. **Analyze**: Understand the request
   - Read the `content` field from JSON
   - Identify the user's intent and required actions

3. **Execute**: Perform the requested action
   - Use available tools (file edits, search, commands)
   - If the request is a question, formulate a concise answer

4. **Respond**: Speak the result via TTS
   - Create a temp briefing file with the response text
   - Create a minimal prompt file (required by `--briefing-file`)
   ```bash
   echo "Acknowledge the response" > /tmp/ae_prompt.md
   echo "---\nvoice: Puck\nstyle: brief, conversational\n---\n\nI have completed the task. The file has been updated." > /tmp/ae_response.md
   agent-ear --non-interactive --prompt-file /tmp/ae_prompt.md --briefing-file /tmp/ae_response.md
   ```
   - Keep responses brief and conversational

5. **Loop or Exit**
   - If the user said "stop", "done", "that's all" → exit voice mode
   - Otherwise → return to Step 1

> [!WARNING]
> During Step 1 (Listen), the command appears to hang while recording.
> This is EXPECTED — do NOT cancel. Wait for the user to stop recording.
