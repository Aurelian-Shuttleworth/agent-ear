"""CLI entry point for agent-ear.

Exposes the full agentic listening pipeline via command-line flags.

Exit codes:
  0 — Success
  1 — Error (recording, transcription, or general failure)
  2 — Prompt validation failed (agent should refine and retry)
"""

import argparse
import sys

from agent_ear import run_pipeline
from config import (
    DEFAULT_LOCATION,
    DEFAULT_TRANSCRIPTION_MODEL,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Extracted for testability — allows testing argument parsing
    without invoking main().
    """
    parser = argparse.ArgumentParser(
        description="Agentic voice capture — agent-steerable audio transcription",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # Standalone mode (identical to 'listen'):
  agent-ear --auto

  # Prompted mode (constrained transcription):
  agent-ear --prompt-file requirements.txt --auto

  # Full agentic mode (TTS briefing + constrained transcription):
  agent-ear --prompt-file requirements.txt --briefing-file brief.md --auto

  # Video transcription:
  agent-ear --video recording.mp4 --auto

  # YouTube analysis:
  agent-ear --video "https://youtube.com/watch?v=..." --high-res --auto

  # Save to a specific directory:
  agent-ear --output-dir ~/Documents/notes --auto

environment variables:
  AGENT_EAR_OUTPUT_DIR   Default output directory for saved notes.
                         Overridden by --output-dir if provided.
  AGENT_EAR_GCS_BUCKET   GCS bucket override (any auth mode, any file size).
                         Overridden by --gcs-bucket if provided.
  AGENT_EAR_THINKING_LEVEL  Override thinking level (minimal/low/medium/high).
                         Overridden by --thinking-level if provided.
  GOOGLE_API_KEY         Google AI Studio API key (no GCP project needed).
  GOOGLE_CLOUD_PROJECT   GCP project ID for Vertex AI mode.

output directory resolution (highest priority first):
  1. --output-dir flag
  2. $AGENT_EAR_OUTPUT_DIR environment variable
  3. Current working directory

authentication resolution (highest priority first):
  1. Vertex AI — if --project-id or $GOOGLE_CLOUD_PROJECT is set (uses ADC)
  2. Google AI Studio — if $GOOGLE_API_KEY is set (simpler, no GCP needed)

upload strategy:
  --gcs-bucket provided → GCS upload (any auth, any size)
  Otherwise, fully automatic:
    ≤ 100 MB → Inline (fastest)
    > 100 MB + Vertex AI → GCS (auto-derived from project)
    > 100 MB + AI Studio → Gemini Files API (up to 2 GB, free)

exit codes:
  0  Success
  1  Error (recording, transcription, or general failure)
  2  Prompt validation failed (agent should refine and retry)
""",
    )

    # Agentic inputs
    agentic = parser.add_argument_group("agentic inputs")
    agentic.add_argument(
        "--prompt-file",
        metavar="FILE",
        help="System prompt file for constrained transcription",
    )
    agentic.add_argument(
        "--prompt",
        metavar="TEXT",
        help="System prompt as inline text",
    )
    agentic.add_argument(
        "--briefing-file",
        metavar="FILE",
        help="TTS briefing file (spoken to user before recording)",
    )
    agentic.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip prompt validation step",
    )

    # Media inputs
    media = parser.add_argument_group("media inputs")
    media.add_argument(
        "--input-file",
        metavar="FILE",
        help="Existing audio file (skip recording)",
    )
    media.add_argument(
        "--video",
        metavar="FILE_OR_URL",
        help="Video file or YouTube URL",
    )

    # Output
    output = parser.add_argument_group("output")
    output.add_argument(
        "--output-dir",
        metavar="DIR",
        default=None,
        help="Output directory (default: $AGENT_EAR_OUTPUT_DIR or cwd)",
    )
    output.add_argument(
        "--output-format",
        metavar="FMT",
        choices=["markdown", "json", "raw"],
        default="markdown",
        help="Output format: markdown|json|raw (default: markdown)",
    )
    output.add_argument(
        "--auto",
        action="store_true",
        help="Skip interactive topic prompt",
    )

    # Model/project
    model_group = parser.add_argument_group("model/project")
    model_group.add_argument(
        "--model",
        metavar="MODEL",
        help=f"Override transcription model (default: {DEFAULT_TRANSCRIPTION_MODEL})",
    )
    model_group.add_argument(
        "--project-id",
        metavar="ID",
        help="Google Cloud Project ID (overrides GOOGLE_CLOUD_PROJECT)",
    )
    model_group.add_argument(
        "--location",
        metavar="LOC",
        default=DEFAULT_LOCATION,
        help=f"Gemini AI location (default: {DEFAULT_LOCATION})",
    )
    model_group.add_argument(
        "--gcs-bucket",
        metavar="BUCKET",
        help="GCS bucket override for large file staging",
    )
    model_group.add_argument(
        "--thinking-level",
        metavar="LEVEL",
        choices=["minimal", "low", "medium", "high"],
        default=None,
        help="Override thinking level (default: auto from validator or duration)",
    )

    # Recording
    recording = parser.add_argument_group("recording")
    recording.add_argument(
        "--high-res",
        action="store_true",
        help="MEDIA_RESOLUTION_HIGH for text-heavy video",
    )
    recording.add_argument(
        "--max-tokens",
        metavar="N",
        type=int,
        default=None,
        help="Max output tokens for transcription (default: 8192 audio, 16384 video)",
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Validation
    if args.briefing_file and not (args.prompt_file or args.prompt):
        parser.error("--briefing-file requires --prompt-file or --prompt")

    try:
        result = run_pipeline(
            prompt_file=args.prompt_file,
            prompt_text=args.prompt,
            briefing_file=args.briefing_file,
            input_file=args.input_file,
            video=args.video,
            output_dir=args.output_dir,
            output_format=args.output_format,
            model=args.model,
            project_id=args.project_id,
            location=args.location,
            validate=not args.no_validate,
            auto=args.auto,
            high_res=args.high_res,
            gcs_bucket=args.gcs_bucket,
            max_tokens=args.max_tokens,
            thinking_level=args.thinking_level,
        )
        sys.exit(result.get("exit_code", 0))

    except KeyboardInterrupt:
        print("\n🛑 Interrupted.", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"\n❌ {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
