"""Output module — file saving, slug extraction, and Obsidian frontmatter wrapping.

Handles:
  - Saving transcription output as markdown, JSON, or raw text
  - Extracting slug from YAML frontmatter
  - Sequential file numbering to prevent overwrites
  - Obsidian final pass (LLM-powered frontmatter generation)
"""

import json
import os
import re
import sys

from google import genai
from google.genai import types

from config import DEFAULT_VALIDATION_MODEL
from cost_tracker import CostTracker


OBSIDIAN_WRAP_PROMPT = """\
You are an Obsidian Note Formatter fixing the layout of raw text transcriptions.

STRATEGY:
1. Read the provided raw text completely.
2. Generatively create the appropriate YAML frontmatter fields (slug, tags).
3. Prepend the frontmatter to the raw text.

OUTPUT FORMAT:
---
slug: kebab-case-summary-of-the-content
tags: [3-5 relevant kebab-case tags, ALWAYS include #audio-note and #inbox]
creation_date: {date}
status: inbox
category: To Process
---
[EXACT ORIGINAL CONTENT]

GUIDELINES:
- Output MUST start with `---` (YAML frontmatter delimiter).
- Preserve the original content EXACTLY character-for-character.
- If the content lacks section headers, add a single "## Content" header.
- Provide NO pleasantries or surrounding text.

DO NOT:
- Alter, summarise, truncate, or hallucinate the main content body.
- Output anything other than the final formatted Markdown string."""


def extract_slug(content: str, default: str = "untitled") -> str:
    """Extract slug from YAML frontmatter if present.

    Args:
        content: Full document content (may include YAML frontmatter).
        default: Fallback slug if none found.

    Returns:
        Slug string.
    """
    match = re.search(r"^slug:\s*(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return default


def save_markdown(
    content: str, output_dir: str, safe_date: str, non_interactive: bool
) -> str:
    """Save transcription as Obsidian markdown note.

    Args:
        content: Transcription content.
        output_dir: Directory to save to.
        safe_date: Date string for filename.
        non_interactive: If True, skip interactive topic prompt.

    Returns:
        Path to saved file.
    """
    slug = extract_slug(content, "untitled")

    if not non_interactive:
        try:
            topic = input("\n📝 Topic (press Enter for auto): ").strip()
            if topic:
                slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
        except (EOFError, KeyboardInterrupt):
            pass

    # Count existing notes for numbering
    existing = [f for f in os.listdir(output_dir) if f.startswith(safe_date)]
    seq = len(existing) + 1
    filename = f"{safe_date}_{seq:03d}_{slug}.md"
    output_path = os.path.join(output_dir, filename)

    with open(output_path, "w") as f:
        f.write(content)
    print(f"\n✅ Note saved: {output_path}")
    return output_path


def save_json(
    content: str, output_dir: str, safe_date: str, non_interactive: bool
) -> str:
    """Save transcription as structured JSON.

    Args:
        content: Transcription content.
        output_dir: Directory to save to.
        safe_date: Date string for filename.
        non_interactive: If True, reserved for future interactive features.

    Returns:
        Path to saved file.
    """
    slug = extract_slug(content, "untitled")
    existing = [f for f in os.listdir(output_dir) if f.startswith(safe_date)]
    seq = len(existing) + 1
    filename = f"{safe_date}_{seq:03d}_{slug}.json"
    output_path = os.path.join(output_dir, filename)

    data = {
        "date": safe_date,
        "slug": slug,
        "format": "json",
        "content": content,
    }
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n✅ JSON saved: {output_path}")
    return output_path


def save_raw(
    content: str, output_dir: str, safe_date: str, non_interactive: bool
) -> str:
    """Save raw transcript text.

    Args:
        content: Raw transcription content.
        output_dir: Directory to save to.
        safe_date: Date string for filename.
        non_interactive: If True, reserved for future interactive features.

    Returns:
        Path to saved file.
    """
    existing = [f for f in os.listdir(output_dir) if f.startswith(safe_date)]
    seq = len(existing) + 1
    filename = f"{safe_date}_{seq:03d}_transcript.txt"
    output_path = os.path.join(output_dir, filename)

    with open(output_path, "w") as f:
        f.write(content)
    print(f"\n✅ Transcript saved: {output_path}")
    return output_path


def obsidian_final_pass(
    client: genai.Client,
    content: str,
    safe_date: str,
    tracker: CostTracker,
) -> str:
    """Wrap raw transcription output in Obsidian frontmatter.

    Uses flash-lite for minimal cost. Preserves content verbatim,
    only adding YAML frontmatter with slug, tags, creation_date, etc.

    Args:
        client: Configured google-genai Client.
        content: Raw transcription text lacking frontmatter.
        safe_date: Date string for frontmatter.
        tracker: CostTracker for usage tracking.

    Returns:
        Content with YAML frontmatter prepended, or original content on failure.
    """
    model = DEFAULT_VALIDATION_MODEL  # flash-lite — cheapest option

    try:
        response = client.models.generate_content(
            model=model,
            contents=f"<content>\n{content}\n</content>",
            config=types.GenerateContentConfig(
                system_instruction=OBSIDIAN_WRAP_PROMPT.format(date=safe_date),
                temperature=0.0,
            ),
        )
        tracker.track(model, response)
        wrapped = response.text.strip()

        # Validate output starts with frontmatter
        if wrapped.startswith("---"):
            print("✅ Obsidian frontmatter added")
            return wrapped
        else:
            print("⚠️  Final pass didn't produce frontmatter, using original content")
            return content

    except Exception as e:
        print(f"⚠️  Obsidian final pass failed: {e}", file=sys.stderr)
        return content
