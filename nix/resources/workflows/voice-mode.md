---
description: Enter voice interaction mode — listen to the user, execute their request, and respond with speech.
---

> **Skills Used:** `@agent-ear`

1. **Listen**:
    - Run `agent-ear` to capture the user's voice:
    - **Audio Only**: `agent-ear --auto`
    - **Video/YouTube**: `agent-ear --auto --video <file_or_url>`
    - **With Briefing**: `agent-ear --auto --briefing-file briefing.md`
    - **Cross-workspace**: `nix run github:Aurelian-Shuttleworth/agent-ear -- --auto`
    - Wait for the user to finish speaking and stop the recording.

2. **Analyze**:
    - Read the generated Markdown transcript file.
    - Understand the user's request from the **Transcript** section.

3. **Execute**:
    - Perform the requested action using available tools.
    - If the request is a simple question, formulate a concise answer.

4. **Respond**:
    - Use `agent-ear` with a briefing file to speak the response:
      ```bash
      echo "I have completed the task." > /tmp/response.md
      agent-ear --auto --briefing-file /tmp/response.md
      ```
    - Keep the response brief and conversational.
