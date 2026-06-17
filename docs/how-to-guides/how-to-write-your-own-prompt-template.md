# How to Write Your Own Prompt Template

This guide shows you how to create a custom prompt template that appears in the wizard's **📋 Templates ▸** menu, so a transcription style you use repeatedly becomes a one-keystroke choice.

## Prerequisites

- `agent-ear` installed (see [README](../../README.md))
- Familiarity with the wizard — see [How to Use the Interactive Wizard](how-to-use-interactive-terminal-wizard.md)

## Template anatomy

A template is a single `.md` file: YAML frontmatter describing the menu entry, followed by the prompt body sent to the transcription model.

```markdown
---
name: Standup Notes
icon: 🏃
description: Daily standup — yesterday, today, blockers per speaker
tags: standup, team
---
You are transcribing a daily standup meeting.

<instructions>
1. For each speaker, capture three sections: Yesterday, Today, Blockers.
2. Label speakers as Person 1, Person 2, etc. based on distinct voices.
3. After all speakers, list any cross-team blockers mentioned.
</instructions>

<output_structure>
## Standup — [Person]

**Yesterday:** …
**Today:** …
**Blockers:** …
</output_structure>

<constraints>
- DO NOT infer blockers that were not explicitly spoken.
- DO NOT summarise away concrete commitments — keep names and dates.
</constraints>
```

| Frontmatter field | Required | Purpose |
|:------------------|:---------|:--------|
| `name` | yes | Menu label in the template picker |
| `icon` | yes | Emoji shown before the name |
| `description` | yes | One-line summary (shown in the packaged template docs; keep it short) |
| `tags` | no | Comma-separated tags merged into the output note's Obsidian frontmatter (in addition to `#audio-note` and `#inbox`) |

## Steps

### 1. Create a templates directory

```bash
mkdir -p ~/agent-ear-templates
```

Copy a packaged template as a starting point — the repository's [`templates/`](../../templates/) directory has six to choose from, and `templates/internal/` shows the structure used for video and audio ingestion.

### 2. Write the template

Save your template as a `.md` file at the top level of that directory (subdirectories are not scanned). Follow the packaged templates' structure: `<instructions>`, `<output_structure>`, and `<constraints>` sections keep the model grounded.

### 3. Point agent-ear at your directory

```bash
export AGENT_EAR_TEMPLATES_DIR=~/agent-ear-templates
agent-ear
```

Your templates now populate the **📋 Templates ▸** menu in place of the packaged set.

> [!NOTE]
> `AGENT_EAR_TEMPLATES_DIR` replaces the packaged directory entirely — it is not merged. If you want the built-in templates alongside your own, copy them into your directory first.

### 4. Test it

Select your template in the wizard and use **🔍 View prompt** on the confirmation screen to verify the body loaded exactly as written. Template runs skip prompt validation (curated templates are treated as pre-validated), so mistakes in the prompt go straight to the transcription model — review the first output carefully.

## Writing effective template prompts

- **State the role and task in the first line** ("You are transcribing a …").
- **Number the instructions** and keep each one a single obligation.
- **Define the output structure literally** — the model mirrors the headings you show it.
- **Constrain hallucination explicitly**: forbid inferring content that was not spoken.
- Keep timestamps, speaker labels, and formatting rules in the instructions, not the description.
