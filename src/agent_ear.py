"""Core agentic listening engine — orchestrates validate → brief → record → transcribe.

This is the heart of agent-ear. It coordinates:
1. Prompt validation (optional, LLM-as-a-judge)
2. TTS briefing (optional, Director's Notes)
3. Audio recording (sounddevice InputStream)
4. Constrained transcription (Gemini, system_instruction separation)

Design informed by:
  - transcribe_note.py (recording, upload, API patterns)
  - Gemini 3 best practices (system_instruction separation, XML tags)
  - Daily Smart Briefing (TTS pipeline)
"""

import os
import shutil
import sys
from datetime import datetime

from briefing import parse_briefing_file, play_briefing
from config import (
    DEFAULT_LOCATION,
    DEFAULT_TRANSCRIPTION_MODEL,
    DEFAULT_VALIDATION_MODEL,
    create_client,
    resolve_config,
    resolve_output_dir,
)
from cost_tracker import CostTracker
from output import obsidian_final_pass, save_json, save_markdown, save_raw
from prompt_validator import validate_briefing, validate_prompt
from recording import SleepPrevention, record_audio
from transcription import build_default_system_prompt, transcribe
from video import YOUTUBE_PATTERN, preprocess_video


def run_pipeline(
    prompt_file: str | None = None,
    prompt_text: str | None = None,
    briefing_file: str | None = None,
    input_file: str | None = None,
    video: str | None = None,
    output_dir: str | None = None,
    output_format: str = "markdown",
    model: str | None = None,
    project_id: str | None = None,
    location: str = DEFAULT_LOCATION,
    validate: bool = True,
    non_interactive: bool = False,
    high_res: bool = False,
    gcs_bucket: str | None = None,
    max_tokens: int | None = None,
    thinking_level: str | None = None,
    template_tags: str | None = None,
    cli_extra_tokens: int = 0,
) -> dict:
    """Run the full agentic listening pipeline.

    Returns:
        dict with keys: output_path, content, format, cost, validation_result
    """
    result = {
        "output_path": None,
        "content": None,
        "format": output_format,
        "cost": 0.0,
        "validation_result": None,
        "exit_code": 0,
    }

    # Global cost tracker — threads through all Gemini calls
    # Resolve pricing cache: shell may have set PRICETOKEN_CACHE,
    # otherwise fetch pricing directly for non-interactive mode.
    pricing_cache = os.environ.get("PRICETOKEN_CACHE")
    if not pricing_cache:
        try:
            from pricing import fetch_pricing, write_pricing_cache

            pricing = fetch_pricing()
            pricing_cache = write_pricing_cache(pricing)
        except Exception:
            pricing_cache = None  # Graceful fallback to hardcoded rates

    tracker = CostTracker(pricing_cache=pricing_cache)

    # --- 0. Config resolution ---
    resolved_project, resolved_location = resolve_config(project_id, location)

    # --- 0.5 Client initialization (Vertex AI → API key fallback) ---
    client, is_vertex = create_client(resolved_project, resolved_location)
    if client is None:
        print(
            "❌ No authentication configured.\n"
            "Either:\n"
            "  • Set GOOGLE_API_KEY for Google AI Studio\n"
            "  • Set GOOGLE_CLOUD_PROJECT + run: gcloud auth application-default login\n"
            "  • Run: gcloud config set project <PROJECT_ID>",
            file=sys.stderr,
        )
        result["exit_code"] = 1
        return result

    mode_label = f"Vertex AI (Project: {resolved_project})" if is_vertex else "Google AI Studio (API key)"
    print(f"🔑 Auth: {mode_label}")

    # --- 1. Load agent prompt ---
    agent_prompt = _load_prompt(prompt_file, prompt_text)

    # --- 2. Validate effective prompt and extract thinking hints ---
    # Validation runs on the effective prompt (agent-provided or default).
    # Only --no-validate suppresses this; --non-interactive has no effect on validation.
    validator_thinking_hint = None
    validator_extra_tokens = 0
    is_video = bool(video)

    if validate:
        # Determine the effective prompt that will be sent to the model
        safe_date_for_prompt = datetime.now().strftime("%Y-%m-%d")
        effective_prompt = agent_prompt or build_default_system_prompt(safe_date_for_prompt, is_video)

        print("🔍 Validating prompt...")
        vr, vr_response = validate_prompt(client, effective_prompt)
        result["validation_result"] = vr
        if vr_response:
            tracker.track(DEFAULT_VALIDATION_MODEL, vr_response)

        # Hard-fail only on agent-provided prompts (default is known-good)
        if agent_prompt and not vr.valid:
            print(f"❌ Prompt validation failed (score: {vr.score}/5)")
            print(f"   Feedback: {vr.feedback}")
            if vr.improved_prompt:
                print(f"   Suggested improvement:\n{vr.improved_prompt}")
            result["exit_code"] = 2
            return result

        print(f"✅ Prompt validated (score: {vr.score}/5)")

        # Extract thinking hints regardless of prompt source
        validator_thinking_hint = vr.thinking_level
        validator_extra_tokens = vr.extra_tokens
        if validator_thinking_hint:
            print(
                f"🧠 Validator recommends thinking_level='{validator_thinking_hint}', "
                f"extra_tokens=+{validator_extra_tokens}"
            )

    # Resolve CLI extra tokens: CLI flag → env var → 0
    resolved_cli_extra = cli_extra_tokens or int(os.environ.get("AGENT_EAR_EXTRA_TOKENS", 0))

    # Stack validator + CLI extra tokens, clamp to 0–16384
    total_extra_tokens = min(max(validator_extra_tokens + resolved_cli_extra, 0), 16384)
    if resolved_cli_extra > 0:
        print(
            f"📏 Extra tokens: +{validator_extra_tokens} (validator) "
            f"+ {resolved_cli_extra} (CLI/env) = +{total_extra_tokens}"
        )

    # --- 2.5 Validate briefing (if provided and validation enabled) ---
    briefing_text = None
    director_notes = None
    if briefing_file:
        briefing_text, director_notes = parse_briefing_file(briefing_file)

        if validate:
            print("🔍 Validating TTS briefing...")
            bvr, bvr_response = validate_briefing(client, briefing_text, director_notes)
            result["briefing_validation_result"] = bvr
            if bvr_response:
                tracker.track(DEFAULT_VALIDATION_MODEL, bvr_response)

            for w in bvr.warnings:
                print(f"   ⚠️  {w}")

            if not bvr.valid:
                print(f"⚠️  Briefing validation warning (score: {bvr.score}/5)")
                print(f"   {bvr.feedback}")

            # Auto-fix: apply suggested improvements
            if bvr.improved_text:
                print("   ✏️  Auto-fixing briefing text")
                briefing_text = bvr.improved_text
            if bvr.improved_notes:
                print(f"   ✏️  Auto-fixing director notes: {bvr.improved_notes}")
                director_notes = {**(director_notes or {}), **bvr.improved_notes}

            print(f"{'✅' if bvr.valid else '⚠️'} Briefing validated (score: {bvr.score}/5)")

    # --- 3. TTS briefing (if briefing text available) ---
    if briefing_text:
        success = play_briefing(
            client=client,
            briefing_text=briefing_text,
            director_notes=director_notes,
            project_id=resolved_project,
            location=resolved_location,
        )
        if not success:
            print("⚠️  TTS briefing failed, continuing to recording...", file=sys.stderr)

    # --- 4. Record or load audio ---
    is_youtube = bool(video and YOUTUBE_PATTERN.match(video))
    is_fresh_recording = False  # Track whether we recorded new audio
    recovery_path = None  # Persistent copy of the recording

    with SleepPrevention():
        if video:
            media_path = preprocess_video(video)
        elif input_file:
            media_path = input_file
        else:
            media_path = record_audio()
            is_fresh_recording = True

            # --- 4.5 Safety copy: persist recording outside /tmp ---
            # macOS aggressively cleans /tmp — save to a durable location
            # immediately so the recording survives crashes.
            resolved_out = resolve_output_dir(output_dir)
            recovery_dir = os.path.join(resolved_out, ".recovery")
            os.makedirs(recovery_dir, exist_ok=True)
            safe_date_for_recovery = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            recovery_path = os.path.join(recovery_dir, f"recording_{safe_date_for_recovery}.wav")
            shutil.copy2(media_path, recovery_path)
            print(f"🛡️  Recording backed up: {recovery_path}")

        # --- 5. Transcribe ---
        safe_date = datetime.now().strftime("%Y-%m-%d")
        model_name = model or DEFAULT_TRANSCRIPTION_MODEL

        # Resolve effective thinking level: CLI override → validator hint
        effective_thinking = thinking_level or validator_thinking_hint

        try:
            content = transcribe(
                client=client,
                media_path=media_path,
                project_id=resolved_project,
                is_vertex=is_vertex,
                model_name=model_name,
                agent_prompt=agent_prompt,
                safe_date=safe_date,
                is_video=is_video,
                is_youtube=is_youtube,
                high_res=high_res,
                gcs_bucket=gcs_bucket,
                output_format=output_format,
                tracker=tracker,
                non_interactive=non_interactive,
                max_tokens=max_tokens,
                thinking_level=effective_thinking,
                extra_tokens=total_extra_tokens,
            )
        except Exception:
            # Recording is safe — tell the user where to find it
            if recovery_path and os.path.exists(recovery_path):
                print(
                    f"\n🛡️  Recording preserved at: {recovery_path}",
                    file=sys.stderr,
                )
                print(
                    f"   Re-run with: agent-ear --input-file '{recovery_path}' "
                    f"{'--prompt-file ' + prompt_file if prompt_file else ''} --non-interactive",
                    file=sys.stderr,
                )
            raise

    # --- 5.5 Obsidian final pass (if raw output lacks frontmatter) ---
    if output_format == "markdown" and not content.strip().startswith("---"):
        print("📝 Adding Obsidian frontmatter via final pass...")
        content = obsidian_final_pass(client, content, safe_date, tracker, template_tags=template_tags)

    result["content"] = content
    result["cost"] = tracker.total_cost_usd

    # --- 6. Save output ---
    output_dir = resolve_output_dir(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    if output_format == "json":
        result["output_path"] = save_json(content, output_dir, safe_date, non_interactive)
    elif output_format == "raw":
        result["output_path"] = save_raw(content, output_dir, safe_date, non_interactive)
    else:
        result["output_path"] = save_markdown(content, output_dir, safe_date, non_interactive)

    # --- 7. Cost summary ---
    tracker.print_summary()

    # --- 8. Cleanup: only on FULL success ---
    # Remove temp recording from /tmp
    if is_fresh_recording and media_path and os.path.exists(media_path):
        try:
            os.remove(media_path)
        except OSError:
            pass
    # Remove recovery copy (output was saved successfully)
    if recovery_path and os.path.exists(recovery_path):
        try:
            os.remove(recovery_path)
            # Clean up .recovery dir if empty
            recovery_dir = os.path.dirname(recovery_path)
            if not os.listdir(recovery_dir):
                os.rmdir(recovery_dir)
        except OSError:
            pass

    return result


def _load_prompt(prompt_file: str | None, prompt_text: str | None) -> str | None:
    """Load agent prompt from file or inline text."""
    if prompt_file:
        with open(prompt_file) as f:
            return f.read().strip()
    if prompt_text:
        return prompt_text.strip()
    return None
