"""Prompt and briefing validation via LLM-as-a-judge pattern.

Uses gemini-3.5-flash for cost-efficient single-shot
evaluation of agent-generated system prompts and TTS briefings.

Design informed by:
- Google's pointwise text quality rubric
- Google's prompt evaluation documentation
- Gemini 3 prompting best practices (XML-style tags, grounding clauses)
- Google TTS Prompting Guide (alignment, naturalness, pacing)
"""

import json
import re
import sys
from dataclasses import dataclass, field

from google import genai
from google.genai import types

from config import DEFAULT_VALIDATION_MODEL


@dataclass
class ValidationResult:
    """Result of prompt validation.

    Includes optional transcription hints emitted by the validator LLM
    to configure the downstream transcription model's reasoning effort
    and output token budget.
    """

    valid: bool
    score: int  # 1-5 pointwise quality score
    feedback: str  # Human-readable feedback for the agent
    improved_prompt: str | None = None  # Optional improved version
    thinking_level: str | None = None  # "low", "medium", "high" hint
    extra_tokens: int = 0  # Additive token budget adjustment (0-16384)


@dataclass
class BriefingValidationResult:
    """Result of TTS briefing validation."""

    valid: bool
    score: int  # 1-5
    feedback: str
    warnings: list[str] = field(default_factory=list)  # Static check warnings
    improved_text: str | None = None
    improved_notes: dict | None = None  # Suggested director notes fix


VALIDATOR_SYSTEM_PROMPT = """\
You are a prompt quality evaluator for audio transcription systems.

<task>
Evaluate whether the following prompt would effectively constrain a
multimodal AI model (Gemini) to extract the RIGHT information from
spoken audio input. The prompt will be used as a system instruction
for audio transcription.
</task>

<criteria>
1. INSTRUCTION CLARITY: Does the prompt clearly specify what information
   to extract? (e.g., "extract user stories" vs vague "process the audio")
2. OUTPUT STRUCTURE: Does it define the expected output format?
   (e.g., markdown sections, YAML frontmatter, explicit depth minimums)
3. GROUNDING: Does it explicitly instruct the model to stay grounded,
   including a MANDATORY requirement to reference explicit timestamps (MM:SS)?
4. NEGATIVE CONSTRAINTS: Does it provide explicit DO NOT guidelines
   describing what the model should avoid (e.g., shallow summaries)?
5. COMPLETENESS: Does it handle edge cases like multiple speakers,
   silence, or background noise?
</criteria>

<transcription_hints>
Based on the prompt's complexity, estimate the optimal configuration
for the downstream transcription model:
- thinking_level: "low" for simple extraction or verbatim transcription,
  "medium" for structured multi-section output with formatting constraints,
  "high" for complex multi-speaker analysis, cross-referencing, or prompts
  requiring deep logical reasoning and exhaustive annotations.
- extra_tokens: integer (0-16384) of ADDITIONAL output tokens the
  transcription model should reserve beyond the duration-based default.
  Use 0 for simple prompts, 2048-4096 for prompts with structured
  sections or YAML frontmatter, 8192+ for prompts demanding exhaustive
  multi-speaker verbatim transcription with annotations.
</transcription_hints>

<output_format>
Return a JSON object with exactly these fields:
- "score": integer 1-5 (1=very poor, 5=excellent)
- "valid": boolean (true if score >= {min_score})
- "feedback": string with specific, actionable improvement suggestions
- "improved_prompt": string with an improved version (only if score < {min_score}, otherwise null)
- "thinking_level": string ("low", "medium", or "high") — recommended reasoning depth for the transcription model
- "extra_tokens": integer 0-16384 — additional output tokens to reserve
</output_format>

Return ONLY the JSON object, no markdown fences, no commentary."""


BRIEFING_VALIDATOR_SYSTEM_PROMPT = """\
You are a TTS briefing quality evaluator for Gemini text-to-speech.

<task>
Evaluate whether the following briefing text and director notes will
produce natural, pleasant-sounding spoken audio via Gemini TTS.
</task>

<criteria>
1. ALIGNMENT: Does the text tone match the director notes?
   (e.g., casual text + "pace: slowly" = robotic over-enunciation)
2. NATURALNESS: Will this sound natural when read aloud?
   (markdown syntax, URLs, code, abbreviations sound wrong in TTS)
3. PACING: Is the pace appropriate for the text length and style?
   ("slowly" works for long formal content, not short casual greetings)
4. SPEAKABILITY: Does the text avoid non-speakable content?
   (tables, bullet lists, technical notation, emojis)
5. LENGTH: Is the text an appropriate length for TTS?
   (>500 words risks timeouts and listener fatigue)
</criteria>

<context>
The TTS system uses Gemini with director's notes that control style,
pace, and voice. Common issues:
- "pace: slowly" with short casual text → over-enunciation
- Markdown headers/formatting in text → spoken as literal characters
- Very long text → TTS timeout or degraded quality
- Mismatch between formal director notes and casual text tone
</context>

<output_format>
Return a JSON object with exactly these fields:
- "score": integer 1-5 (1=will sound terrible, 5=will sound great)
- "valid": boolean (true if score >= {min_score})
- "feedback": string with specific improvements
- "improved_text": string with improved briefing text (only if text needs fixing, otherwise null)
- "improved_notes": object with suggested director notes changes (only if notes need fixing, otherwise null)
  Example: {{"pace": "naturally", "style": "warm and conversational"}}
</output_format>

Return ONLY the JSON object, no markdown fences, no commentary."""


def validate_prompt(
    client: genai.Client,
    prompt: str,
    model: str = DEFAULT_VALIDATION_MODEL,
    min_score: int = 3,
) -> tuple[ValidationResult, object | None]:
    """Validate an agent-generated prompt using LLM-as-a-judge.

    Args:
        client: Configured google-genai Client.
        prompt: The system prompt to validate.
        model: Model for validation (default: flash-lite for cost).
        min_score: Minimum passing score (1-5, default: 3).

    Returns:
        Tuple of (ValidationResult, Gemini response or None).
    """
    if not prompt or not prompt.strip():
        return ValidationResult(
            valid=False,
            score=0,
            feedback="Prompt is empty. Provide a system instruction that specifies "
            "what information to extract from the audio.",
        ), None

    system_instruction = VALIDATOR_SYSTEM_PROMPT.format(min_score=min_score)

    try:
        response = client.models.generate_content(
            model=model,
            contents=f"Evaluate this transcription prompt:\n\n{prompt}",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.0,  # Deterministic evaluation
                response_mime_type="application/json",
            ),
        )
        return _parse_validation_response(response.text, min_score), response

    except Exception as e:
        print(f"⚠️  Prompt validation failed: {e}", file=sys.stderr)
        # Fail open — don't block transcription if validation itself errors
        return ValidationResult(
            valid=True,
            score=3,
            feedback=f"Validation service error: {e}. Proceeding with prompt as-is.",
        ), None


def validate_briefing(
    client: genai.Client,
    briefing_text: str,
    director_notes: dict | None = None,
    model: str = DEFAULT_VALIDATION_MODEL,
    min_score: int = 3,
) -> tuple[BriefingValidationResult, object | None]:
    """Validate a TTS briefing using static checks + LLM-as-a-judge.

    Two-layer validation:
    1. Static pre-checks (no LLM cost) — catches obvious issues instantly
    2. LLM judge — evaluates tone/pacing alignment and naturalness

    Args:
        client: Configured google-genai Client.
        briefing_text: The text to be spoken.
        director_notes: Optional dict with style, pace, format, voice keys.
        model: Model for validation.
        min_score: Minimum passing score.

    Returns:
        Tuple of (BriefingValidationResult, Gemini response or None).
    """
    if not briefing_text or not briefing_text.strip():
        return BriefingValidationResult(
            valid=False,
            score=0,
            feedback="Briefing text is empty.",
        ), None

    # --- Layer 1: Static pre-checks (free, instant) ---
    warnings, static_fixes = _static_briefing_checks(briefing_text, director_notes)

    # --- Layer 2: LLM-as-a-judge (alignment, naturalness) ---
    notes_str = json.dumps(director_notes, indent=2) if director_notes else "None"
    eval_content = (
        f"Evaluate this TTS briefing:\n\n"
        f"<director_notes>\n{notes_str}\n</director_notes>\n\n"
        f"<briefing_text>\n{briefing_text}\n</briefing_text>"
    )

    system_instruction = BRIEFING_VALIDATOR_SYSTEM_PROMPT.format(min_score=min_score)

    try:
        response = client.models.generate_content(
            model=model,
            contents=eval_content,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )
        result = _parse_briefing_validation_response(response.text, min_score)
        llm_response = response
    except Exception as e:
        print(f"⚠️  Briefing validation failed: {e}", file=sys.stderr)
        result = BriefingValidationResult(
            valid=True,
            score=3,
            feedback=f"Validation service error: {e}. Proceeding as-is.",
        )
        llm_response = None

    # Merge static warnings into result
    result.warnings = warnings

    # Apply static fixes if LLM didn't suggest anything
    if static_fixes and not result.improved_notes:
        result.improved_notes = static_fixes
    elif static_fixes and result.improved_notes:
        # Merge: LLM suggestions take priority
        merged = {**static_fixes, **result.improved_notes}
        result.improved_notes = merged

    # Downgrade score if static checks found serious issues
    if any("non-speakable" in w.lower() or "markdown" in w.lower() for w in warnings):
        result.score = min(result.score, 3)
        result.valid = result.score >= min_score

    return result, llm_response


# --- Static pre-checks ---

_MARKDOWN_PATTERNS = [
    (re.compile(r"^#{1,6}\s", re.MULTILINE), "Markdown headers (##)"),
    (re.compile(r"\*\*[^*]+\*\*"), "Bold markdown (**text**)"),
    (re.compile(r"\*[^*]+\*"), "Italic markdown (*text*)"),
    (re.compile(r"^[-*]\s", re.MULTILINE), "Bullet list markers"),
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), "Markdown links"),
]

_URL_PATTERN = re.compile(r"https?://\S+")

# Pacing mismatches: short casual text + slow pace
_SLOW_PACE_KEYWORDS = {"slowly", "slow", "very slowly", "extremely slowly"}


def _static_briefing_checks(
    text: str, notes: dict | None
) -> tuple[list[str], dict | None]:
    """Run fast static checks on briefing content.

    Returns:
        (warnings_list, suggested_notes_fixes_or_None)
    """
    warnings = []
    fixes = {}
    notes = notes or {}

    # Check for markdown remnants
    for pattern, desc in _MARKDOWN_PATTERNS:
        if pattern.search(text):
            warnings.append(f"Non-speakable content: {desc} found in text")

    # Check for URLs
    urls = _URL_PATTERN.findall(text)
    if urls:
        warnings.append(
            f"Non-speakable content: {len(urls)} URL(s) found — "
            "these will be read character-by-character"
        )

    # Check length
    word_count = len(text.split())
    if word_count > 500:
        warnings.append(
            f"Long briefing ({word_count} words) — may cause TTS timeout "
            "or listener fatigue. Consider shortening to <300 words."
        )

    # Check pacing mismatch
    pace = str(notes.get("pace", "")).lower().strip()
    if pace in _SLOW_PACE_KEYWORDS and word_count < 50:
        warnings.append(
            f"Pacing mismatch: '{pace}' pace with short text ({word_count} words) "
            "will cause over-enunciation. Suggest 'naturally' or 'moderate'."
        )
        fixes["pace"] = "naturally"

    return warnings, fixes if fixes else None


# --- Response parsing ---


def _parse_validation_response(text: str, min_score: int) -> ValidationResult:
    """Parse the LLM judge response into a ValidationResult.

    Handles malformed JSON gracefully — returns a conservative result
    with the raw text as feedback rather than crashing.
    """
    try:
        # Strip any markdown fencing if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned[: cleaned.rfind("```")]
            cleaned = cleaned.strip()

        data = json.loads(cleaned)

        score = int(data.get("score", 3))
        score = max(1, min(5, score))  # Clamp to 1-5

        # Parse thinking hints with safe defaults
        raw_level = data.get("thinking_level")
        thinking_level = raw_level if raw_level in ("low", "medium", "high") else None
        try:
            extra_tokens = min(max(int(data.get("extra_tokens", 0)), 0), 16384)
        except (TypeError, ValueError):
            extra_tokens = 0

        return ValidationResult(
            valid=data.get("valid", score >= min_score),
            score=score,
            feedback=data.get("feedback", "No feedback provided."),
            improved_prompt=data.get("improved_prompt"),
            thinking_level=thinking_level,
            extra_tokens=extra_tokens,
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        # Graceful fallback — return the raw text as feedback
        return ValidationResult(
            valid=False,
            score=2,
            feedback=f"Could not parse validation response: {text[:500]}",
        )


def _parse_briefing_validation_response(
    text: str, min_score: int
) -> BriefingValidationResult:
    """Parse the LLM briefing judge response."""
    try:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned[: cleaned.rfind("```")]
            cleaned = cleaned.strip()

        data = json.loads(cleaned)

        score = int(data.get("score", 3))
        score = max(1, min(5, score))

        return BriefingValidationResult(
            valid=data.get("valid", score >= min_score),
            score=score,
            feedback=data.get("feedback", "No feedback provided."),
            improved_text=data.get("improved_text"),
            improved_notes=data.get("improved_notes"),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return BriefingValidationResult(
            valid=False,
            score=2,
            feedback=f"Could not parse validation response: {text[:500]}",
        )
