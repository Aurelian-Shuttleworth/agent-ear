# Context: agent-ear

Shared vocabulary and relationships for agent-ear development and documentation.
Read this before contributing docs or renaming concepts.

## Language

### Architecture

**Prosodic Contextualisation**:
The core differentiator — preserving semantic meaning carried by emphasis, tone, and pacing by sending media directly to a multimodal model rather than through a speech-to-text intermediary.
_Avoid_: transcription, speech-to-text, STT

**Pipeline**:
The full execution sequence from configuration through output — the unit of work that `run_pipeline()` orchestrates (validate → brief → record → transcribe → save).
_Avoid_: workflow, flow, process

**Stage**:
Each numbered step within the Pipeline (e.g. Config, Validate, Record, Transcribe, Save).
_Avoid_: phase, step, task

**Shell**:
The `agent-ear` bash entry point. Routes to the Engine when `--non-interactive` is passed or stdin is not a TTY; otherwise launches the Wizard.
_Avoid_: dispatcher, wrapper, launcher

**Engine**:
The `agent-ear-core` Python backend — the Pipeline implementation. The only component that talks to Gemini. AI agents call this path exclusively.
_Avoid_: backend, core (ambiguous), server

**Validator**:
The LLM-as-a-judge pattern (always the validation model `gemini-3.5-flash`) that scores prompts and briefings before the Pipeline runs. Blocks bad agent prompts; warns on poor briefings. Distinct from the **transcription model**, which the user selects. Runs unless `--no-validate` is passed or a curated Prompt Template is used.
_Avoid_: judge, checker, linter

### User-Facing Concepts

**Mode**:
A TUI selection (Freeform, Meeting, YouTube, etc.) that maps to a Prompt Template and a set of CLI flags. Modes are user-facing presets; the Pipeline is Mode-agnostic.
_Avoid_: preset, profile, option

**Wizard**:
The interactive TUI inside the Shell script, built with [Gum](docs/reference/interactive-tui.md). Two-tier menu since the template engine landed: Record Now / Custom Prompt / Templates ▸ / Transcribe ▸. There is no separate interactive binary (the former `agent-ear-interactive.sh` was deleted).
_Avoid_: interactive mode, TUI (in user-facing docs)

**Prompt Template**:
A `.md` file with YAML frontmatter (`name`, `icon`, `description`, `tags`) and a prompt body, loaded from `AGENT_EAR_TEMPLATES_DIR`. User-facing templates live at the directory root; **internal templates** (`internal/`) are auto-applied by Transcribe Modes and not user-selectable. Selecting a curated template skips validation (`NO_VALIDATE`).
_Avoid_: template (ambiguous with Nix templates), recipe, config file

**AGENT_EAR_TEMPLATES_DIR**:
Environment variable pointing at the Prompt Templates directory. Set by the Nix wrapper to the packaged templates; users may override it to use their own collection.

**Briefing**:
TTS spoken instructions played before recording (`--briefing-file`). CLI-only since the Wizard restructure; the Wizard no longer exposes a briefing Mode.
_Avoid_: instructions, preamble

### Output & Files

**Slug**:
The short kebab-case topic identifier embedded in output filenames (`{date}_{seq}_{slug}.md`). May originate from LLM frontmatter or manual input; all sources are sanitized at filename construction (see ADR 001).
_Avoid_: topic, title, filename

**How-to Guide**:
A Diátaxis task-oriented document in `docs/how-to-guides/`. Convention: filename starts with `how-to-` and the H1 starts with "How to …". Link text in indexes uses the same "How to …" phrasing.

## Relationships

- The **Shell** wraps the **Engine**; the Engine can run standalone, the Wizard cannot produce output without exec-ing the Engine.
- A **Prompt Template** belongs to exactly one templates directory; the Wizard discovers user-facing templates by scanning `AGENT_EAR_TEMPLATES_DIR/*.md` at runtime.
- The **Validator** and the **transcription model** are two separate Gemini calls; the Validator's verdict (score, thinking level, extra tokens) configures the transcription call.
- Each Wizard fact lives in exactly one doc: `docs/reference/interactive-tui.md` is the canonical screen-by-screen spec; `docs/how-to-guides/how-to-use-interactive-terminal-wizard.md` is a slim task walkthrough that links to the reference.
- Doc reading order (index + README): README → Tutorials → How-to Guides → Explanation → Reference.

## Open Questions

- Should there be a second tutorial dedicated to video transcription? (Raised during doc review; parked.)
- Is the exit-code-2 section in `docs/reference/cli.md` clear enough for a developer building an agent that calls agent-ear? (Needs an outside reader; ask during publishing review.)
- Prompt Template how-to scope: does a user-supplied `AGENT_EAR_TEMPLATES_DIR` fully replace the packaged templates (including `internal/`), and is that the supported contract?
