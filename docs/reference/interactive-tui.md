# Interactive TUI Reference

`agent-ear-interactive` provides a guided Terminal UI (TUI) wizard built with [Gum](https://github.com/charmbracelet/gum). This wizard walks human users through configuring and running the transcription pipeline, before delegating to `agent-ear-core --auto`.

This document maps the flow of the interactive wizard and provides layout references.

## Flow Overview

1. **Mode Selection**: Choose the primary action (Record Audio, Meeting, Video, etc.).
2. **Configuration**: Set standard parameters (Output format, Model, Directory, Topic).
3. **Advanced Options (Optional)**: Configure GCS staging, high-res mode, or bypass validation.
4. **Conditional Setup**: Screens triggered by specific modes (e.g., Meeting setup, Prompt file selection).
5. **Confirmation**: A pre-flight summary before execution.

## Screen Mockups

### 1. Mode Selection Menu

The entry point for all interactive sessions.

```
┌────────────────────────────────────────────────────────┐
│  🎙️  Agent-Ear  ·  Interactive Mode                    │
├────────────────────────────────────────────────────────┤
│  What would you like to do?                            │
│                                                        │
│ > 🎤 Record Audio — Freeform voice note                │
│   🤝 Record Meeting — Multi-speaker, action points...  │
│   📝 Record Audio — With a custom prompt               │
│   🗣️ Full Agentic — TTS briefing + recording           │
│   🎬 Transcribe Video — Local file                     │
│   📺 Transcribe YouTube — From URL                     │
│   📂 Transcribe File — Existing audio file             │
│   ❌ Cancel                                            │
└────────────────────────────────────────────────────────┘
```

**Widget Spec:**
- Rendered via: `gum choose`
- State updated: `$MODE`

### 2. Configuration Setup

After selecting a mode, standard configuration options are collected.

```
┌────────────────────────────────────────────────────────┐
│  ⚙️  Configuration                                     │
├────────────────────────────────────────────────────────┤
│ Output format:                                         │
│ > markdown                                             │
│   json                                                 │
│   raw                                                  │
│                                                        │
│ Transcription model:                                   │
│   🟢 Flash-Lite — fast, cheap (default)                │
│ > 🟡 Flash — balanced quality/cost                     │
│   🔴 Pro — premium, expensive                          │
│                                                        │
│ Output directory:                                      │
│ > /home/user/notes____________________________________ │
│                                                        │
│ Topic slug (leave blank for auto-generation):          │
│ > sprint-planning_____________________________________ │
└────────────────────────────────────────────────────────┘
```

**Widget Spec:**
- Formats & Models: `gum choose`
- Directory & Topic: `gum input`
- State updated: `$FORMAT`, `$MODEL`, `$OUTPUT_DIR`, `$TOPIC`

### 3. Conditional: Meeting Setup

Triggered only when the **🤝 Record Meeting** mode is selected.

```
┌────────────────────────────────────────────────────────┐
│  🤝 Meeting Configuration                              │
├────────────────────────────────────────────────────────┤
│  ℹ️ Agent-ear will transcribe a multi-speaker          │
│     conversation, extract action points, and           │
│     capture notable quotes.                            │
│                                                        │
│ How should speakers be identified?                     │
│ > 👤 By name — I'll provide participant names          │
│   🔢 By number — Person 1, Person 2, Person 3...       │
│                                                        │
│ Participant names (comma-separated):                   │
│ > Alice, Bob, Charlie_________________________________ │
└────────────────────────────────────────────────────────┘
```

**Widget Spec:**
- Choice: `gum choose`
- Text Input: `gum input`
- State updated: `$MEETING_NAMES`, injected into `$PROMPT_TEXT`

### 4. Pre-Flight Confirmation

The final screen before `agent-ear-core` is launched. Summarizes all resolved configuration flags.

```
┌────────────────────────────────────────────────────────┐
│  ✅ Ready to go                                        │
├────────────────────────────────────────────────────────┤
│  Mode:     Record Meeting                              │
│  Model:    gemini-3-flash-preview                      │
│  Format:   markdown                                    │
│  Output:   /home/user/notes                            │
│  Topic:    sprint-planning                             │
│  Prompt:   inline: "You are transcribing a multi-sp.." │
│                                                        │
│ Start recording? (Y/n)                                 │
└────────────────────────────────────────────────────────┘
```

**Widget Spec:**
- Rendered via: `gum confirm`
- Action: Assembles `ARGS+=("--output-format" "$FORMAT" ...)` and executes `agent-ear-core "${ARGS[@]}" --auto`
