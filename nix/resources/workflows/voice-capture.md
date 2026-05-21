---
description: Capture structured voice input with optional TTS briefing — one-shot prompted recording.
---

> **Skills Used:** `@agent-ear`, `@agent-ear-capture`, `@agent-ear-briefing`

1. **Prepare Prompt**
   - Create a prompt file defining the transcription constraints
   - Re-read `@agent-ear-capture` for the 5 validation criteria
   - Save as a temp file or in the project directory

2. **(Optional) Prepare Briefing**
   - If the user needs spoken instructions before recording:
   - Create a briefing file with Director's Notes (see `@agent-ear-briefing`)
   - Keep under 500 words to avoid TTS timeout

3. **Execute Capture**
   ```bash
   # With prompt only
   agent-ear --auto --prompt-file prompt.md

   # With TTS briefing + prompt
   agent-ear --auto --prompt-file prompt.md --briefing-file briefing.md
   ```

4. **Verify Output**
   - Check exit code: `0` = success, `2` = prompt failed validation (refine and retry)
   - Read the output markdown file
   - Verify it matches the prompt constraints (sections present, timestamps included, etc.)

5. **Process**
   - Integrate the transcript into the active workflow
   - Move to appropriate location if needed (e.g., Obsidian vault inbox)
   - Use the transcript content for downstream tasks
