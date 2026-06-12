# Context: agent-ear

Shared vocabulary and relationships for agent-ear development and documentation.
Read this before contributing docs or renaming concepts.

## Glossary

**agent-ear**: The Bash dispatcher binary and Gum TUI. The single human-facing entry point. Routes to **agent-ear-core** when `--non-interactive` is passed or stdin is not a TTY; otherwise launches the **wizard**.

**agent-ear-core**: The Python pipeline binary (validate → brief → record → transcribe → save). The only component that talks to Gemini. AI agents call this path exclusively.

**wizard**: The interactive Gum TUI inside the `agent-ear` script. Two-tier menu since the template engine landed: Record Now / Custom Prompt / Templates ▸ / Transcribe ▸. There is no separate interactive binary (the former `agent-ear-interactive.sh` was deleted).

**template**: A `.md` file with YAML frontmatter (`name`, `icon`, `description`, `tags`) and a prompt body, loaded from **AGENT_EAR_TEMPLATES_DIR**. User-facing templates live at the directory root; **internal templates** (`internal/`) are auto-applied by Transcribe modes and not user-selectable. Selecting a curated template skips prompt validation (`NO_VALIDATE`).

**AGENT_EAR_TEMPLATES_DIR**: Environment variable pointing at the templates directory. Set by the Nix wrapper to the packaged templates; users may override it to use their own template collection.

**judge**: The prompt-validation Gemini call (LLM-as-a-judge, always the validation model `gemini-3.5-flash`). Distinct from the **transcription model**, which the user selects. The judge runs unless `--no-validate` is passed or a curated template is used.

**slug**: The short kebab-case topic identifier embedded in output filenames (`{date}_{seq}_{slug}.md`). May originate from LLM frontmatter or manual input; all sources are sanitized at filename construction (see ADR 001).

**how-to guide**: A Diátaxis task-oriented document in `docs/how-to-guides/`. Convention: filename starts with `how-to-` and the H1 starts with "How to …". Link text in indexes uses the same "How to …" phrasing.

**briefing**: TTS spoken instructions played before recording (`--briefing-file`). CLI-only since the wizard restructure; the wizard no longer exposes a briefing mode.

## Relationships

- **agent-ear** wraps **agent-ear-core**; core can run standalone, the wizard cannot produce output without exec-ing core.
- A **template** belongs to exactly one templates directory; the wizard discovers user-facing templates by scanning `AGENT_EAR_TEMPLATES_DIR/*.md` at runtime.
- The **judge** and the **transcription model** are two separate Gemini calls; the judge's verdict (score, thinking level, extra tokens) configures the transcription call.
- Each wizard fact lives in exactly one doc: `docs/reference/interactive-tui.md` is the canonical screen-by-screen spec; `docs/how-to-guides/how-to-use-interactive-mode.md` is a slim task walkthrough that links to the reference.
- Doc reading order (index + README): README → Tutorials → How-to Guides → Explanation → Reference.

## Open Questions

- Should there be a second tutorial dedicated to video transcription? (Raised during doc review; parked.)
- Is the exit-code-2 section in `docs/reference/cli.md` clear enough for a developer building an agent that calls agent-ear? (Needs an outside reader; ask during publishing review.)
- Template how-to scope: does a user-supplied `AGENT_EAR_TEMPLATES_DIR` fully replace the packaged templates (including `internal/`), and is that the supported contract?
