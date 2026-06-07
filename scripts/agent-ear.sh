#!/usr/bin/env bash
# shellcheck shell=bash
# agent-ear — Smart dispatcher & Gum TUI wrapper
#
# This is the main entry point. It first checks for non-interactive
# usage (e.g. --auto or piped input) and delegates directly to the Python core.
# If interactive, it launches the TUI wizard to guide the user.

set -euo pipefail

# ── Early exit: agent/non-interactive paths ──
for arg in "$@"; do
  case "$arg" in
    --auto|--help|-h) exec agent-ear-core "$@" ;;
  esac
done
[[ ! -t 0 ]] && exec agent-ear-core "$@"

# ── Theme ──────────────────────────────────────────────────────────
# Consistent styling tokens
readonly BORDER_COLOR="212"  # Magenta-ish
readonly ACCENT_COLOR="212"
readonly SUCCESS_COLOR="78"  # Green
readonly WARN_COLOR="214"    # Amber
readonly ERROR_COLOR="196"   # Red
readonly DIM_COLOR="240"     # Grey

# ── State ──────────────────────────────────────────────────────────
# Accumulated CLI flags for agent-ear-core
declare -a ARGS=()
MODE=""
MODEL=""
FORMAT=""
OUTPUT_DIR=""
TOPIC=""
PROMPT_TEXT=""
PROMPT_FILE=""
BRIEFING_FILE=""
VIDEO=""
INPUT_FILE=""
HIGH_RES=""
GCS_BUCKET=""
PROJECT_ID=""
LOCATION=""
NO_VALIDATE=""
MEETING_NAMES=""

# ── Helpers ────────────────────────────────────────────────────────

header() {
  echo ""
  gum style --bold --border double \
    --border-foreground "$BORDER_COLOR" --padding "0 2" \
    "🎙️  Agent-Ear  ·  Interactive Mode"
  echo ""
}

info() {
  gum style --foreground "$ACCENT_COLOR" "  ℹ️  $1"
}

success() {
  gum style --foreground "$SUCCESS_COLOR" "  ✅ $1"
}

warn() {
  gum style --foreground "$WARN_COLOR" "  ⚠️  $1"
}

die() {
  gum style --foreground "$ERROR_COLOR" "  ❌ $1"
  exit 1
}

cancelled() {
  echo ""
  gum style --foreground "$DIM_COLOR" --italic "  Cancelled."
  exit 0
}

# ── Screen 1: Mode Selection ──────────────────────────────────────

select_mode() {
  gum style --bold --foreground "$ACCENT_COLOR" \
    "  What would you like to do?"
  echo ""

  MODE=$(gum choose --cursor.foreground "$ACCENT_COLOR" \
    "🎤 Record Audio — Freeform voice note" \
    "🤝 Record Meeting — Multi-speaker, action points & quotes" \
    "📝 Record Audio — With a custom prompt" \
    "🗣️ Full Agentic — TTS briefing + recording" \
    "🎬 Transcribe Video — Local file" \
    "📺 Transcribe YouTube — From URL" \
    "📂 Transcribe File — Existing audio file" \
    "❌ Cancel" \
  ) || cancelled

  [[ "$MODE" == "❌ Cancel" ]] && cancelled

  echo ""
  success "Mode: ${MODE%% —*}"
}

# ── Screen 2: Configuration ───────────────────────────────────────

configure_options() {
  gum style --bold --foreground "$ACCENT_COLOR" \
    "  ⚙️  Configuration"
  echo ""

  # Output format
  FORMAT=$(gum choose --cursor.foreground "$ACCENT_COLOR" \
    --header "Output format:" \
    "markdown" \
    "json" \
    "raw" \
  ) || cancelled
  success "Format: $FORMAT"

  # Model selection
  local model_choice
  model_choice=$(gum choose --cursor.foreground "$ACCENT_COLOR" \
    --header "Transcription model:" \
    "🟢 Flash — fast, balanced (default)" \
    "🟡 Flash-Lite — cheapest, lower quality" \
    "🔴 Pro — premium, expensive" \
  ) || cancelled

  case "$model_choice" in
    *Flash-Lite*) MODEL="gemini-3.1-flash-lite-preview" ;;
    *Flash*)      MODEL="gemini-3.5-flash" ;;
    *Pro*)        MODEL="gemini-3.1-pro-preview" ;;
  esac
  success "Model: $MODEL"

  # Output directory
  local default_dir
  default_dir="${AGENT_EAR_OUTPUT_DIR:-$(pwd)}"
  OUTPUT_DIR=$(gum input --cursor.foreground "$ACCENT_COLOR" \
    --header "Output directory:" \
    --placeholder "$default_dir" \
    --value "$default_dir" \
  ) || cancelled
  # If user cleared the field, fall back to the default
  OUTPUT_DIR="${OUTPUT_DIR:-$default_dir}"
  success "Output: $OUTPUT_DIR"

  # Topic slug (optional)
  TOPIC=$(gum input --cursor.foreground "$ACCENT_COLOR" \
    --header "Topic slug (leave blank for auto-generation):" \
    --placeholder "e.g. sprint-retro-2026-04" \
  ) || cancelled
  if [[ -n "$TOPIC" ]]; then
    success "Topic: $TOPIC"
  else
    gum style --foreground "$DIM_COLOR" "  Topic: [auto-generated]"
  fi

  echo ""

  # Advanced options sub-menu
  local advanced_choice
  advanced_choice=$(gum choose --cursor.foreground "$ACCENT_COLOR" \
    "✅ Continue" \
    "⚙️  Advanced Options (GCS, High-Res, Validation)" \
  ) || cancelled

  if [[ "$advanced_choice" == *"Advanced"* ]]; then
    configure_advanced
  fi

  echo ""
}

# ── Screen 2b: Advanced Options ───────────────────────────────────

configure_advanced() {
  echo ""
  gum style --bold --foreground "$ACCENT_COLOR" \
    "  ⚙️  Advanced Configuration"
  echo ""

  # Skip prompt validation
  if gum confirm --default=false \
    "Skip prompt validation?"; then
    NO_VALIDATE="true"
    warn "Prompt validation: SKIPPED"
  else
    gum style --foreground "$DIM_COLOR" "  Prompt validation: enabled"
  fi

  # High-res mode (for video)
  if gum confirm --default=false \
    "Enable high-resolution mode? (for text-heavy video)"; then
    HIGH_RES="true"
    success "High-res: ON"
  else
    gum style --foreground "$DIM_COLOR" "  High-res: off"
  fi

  # GCS bucket
  GCS_BUCKET=$(gum input --cursor.foreground "$ACCENT_COLOR" \
    --header "GCS staging bucket (leave blank for auto):" \
    --placeholder "my-project-transcribe-staging" \
  ) || cancelled
  if [[ -n "$GCS_BUCKET" ]]; then
    success "GCS Bucket: $GCS_BUCKET"
  else
    gum style --foreground "$DIM_COLOR" "  GCS Bucket: [auto-derived from project]"
  fi

  # Project ID
  PROJECT_ID=$(gum input --cursor.foreground "$ACCENT_COLOR" \
    --header "GCP Project ID (leave blank for auto-detect):" \
    --placeholder "\$GOOGLE_CLOUD_PROJECT or gcloud config" \
  ) || cancelled
  if [[ -n "$PROJECT_ID" ]]; then
    success "Project: $PROJECT_ID"
  fi

  # Location
  LOCATION=$(gum input --cursor.foreground "$ACCENT_COLOR" \
    --header "Gemini API location (leave blank for 'global'):" \
    --placeholder "global" \
  ) || cancelled
  if [[ -n "$LOCATION" ]]; then
    success "Location: $LOCATION"
  fi
}

# ── Screen 3: Conditional Inputs ──────────────────────────────────

collect_meeting_setup() {
  echo ""
  gum style --bold --foreground "$ACCENT_COLOR" \
    "  🤝 Meeting Configuration"
  echo ""

  info "Agent-ear will transcribe a multi-speaker conversation,"
  info "extract action points, and capture notable quotes."
  echo ""

  # Named speakers or generic?
  local speaker_choice
  speaker_choice=$(gum choose --cursor.foreground "$ACCENT_COLOR" \
    --header "How should speakers be identified?" \
    "👤 By name — I'll provide participant names" \
    "🔢 By number — Person 1, Person 2, Person 3, ..." \
  ) || cancelled

  if [[ "$speaker_choice" == *"By name"* ]]; then
    MEETING_NAMES=$(gum input --cursor.foreground "$ACCENT_COLOR" \
      --header "Participant names (comma-separated):" \
      --placeholder "Alice, Bob, Charlie" \
    ) || cancelled

    if [[ -z "$MEETING_NAMES" ]]; then
      warn "No names provided — falling back to Person 1, 2, 3..."
      MEETING_NAMES=""
    else
      success "Participants: $MEETING_NAMES"
    fi
  else
    success "Speakers: numbered (Person 1, 2, 3...)"
  fi

  # Build the meeting system prompt
  local speaker_instruction
  if [[ -n "$MEETING_NAMES" ]]; then
    speaker_instruction="Identify each speaker by their name: ${MEETING_NAMES}. If you cannot distinguish a speaker, label them as 'Unknown Speaker'."
  else
    speaker_instruction="Label speakers as Person 1, Person 2, Person 3, etc. based on distinct voices."
  fi

  PROMPT_TEXT="You are transcribing a multi-speaker meeting.

<instructions>
1. SPEAKER IDENTIFICATION: ${speaker_instruction}
2. TRANSCRIPTION: Provide a full, accurate transcription with speaker labels.
3. ACTION ITEMS: After the transcription, list all action items mentioned.
   Format each as: '- [ ] [Owner]: [Action item description]'
4. NOTABLE QUOTES: Extract 3-5 notable, impactful, or decision-defining quotes.
   Format each as: '> \"[Quote]\" — [Speaker]'
</instructions>

<output_structure>
## Meeting Transcription

[Full speaker-labeled transcription here]

## Action Items

- [ ] [Owner]: [Description]

## Notable Quotes

> \"[Quote]\" — [Speaker]
</output_structure>

Stay grounded in the audio. Do not infer action items or quotes that were not explicitly spoken."
}

collect_prompt() {
  echo ""
  gum style --bold --foreground "$ACCENT_COLOR" \
    "  📝 System Prompt"
  echo ""

  info "The prompt constrains what agent-ear extracts from audio."
  info "e.g. \"Extract action items as bullet points\""
  echo ""

  local prompt_method
  prompt_method=$(gum choose --cursor.foreground "$ACCENT_COLOR" \
    --header "How would you like to provide the prompt?" \
    "✍️  Type inline — Enter prompt text directly" \
    "📄 From file — Select a prompt file" \
    "❌ Cancel" \
  ) || cancelled

  [[ "$prompt_method" == "❌ Cancel" ]] && cancelled

  if [[ "$prompt_method" == *"Type inline"* ]]; then
    PROMPT_TEXT=$(gum write --cursor.foreground "$ACCENT_COLOR" \
      --header "Enter your system prompt:" \
      --placeholder "Describe what to extract from the audio..." \
      --char-limit 4000 \
    ) || cancelled

    if [[ -z "$PROMPT_TEXT" ]]; then
      die "Prompt cannot be empty for this mode."
    fi
    success "Prompt: inline (${#PROMPT_TEXT} chars)"
  else
    info "Select a prompt file..."
    PROMPT_FILE=$(gum file --cursor.foreground "$ACCENT_COLOR" \
      --all \
    ) || cancelled

    if [[ ! -f "$PROMPT_FILE" ]]; then
      die "File not found: $PROMPT_FILE"
    fi
    success "Prompt file: $PROMPT_FILE"
  fi
}

collect_briefing() {
  echo ""
  gum style --bold --foreground "$ACCENT_COLOR" \
    "  🗣️ TTS Briefing"
  echo ""

  info "Select a briefing file to be read aloud before recording."
  echo ""

  BRIEFING_FILE=$(gum file --cursor.foreground "$ACCENT_COLOR" \
    --all \
  ) || cancelled

  if [[ ! -f "$BRIEFING_FILE" ]]; then
    die "File not found: $BRIEFING_FILE"
  fi
  success "Briefing file: $BRIEFING_FILE"
}

collect_video() {
  echo ""
  gum style --bold --foreground "$ACCENT_COLOR" \
    "  🎬 Video File"
  echo ""

  info "Select a local video file to transcribe."
  echo ""

  VIDEO=$(gum file --cursor.foreground "$ACCENT_COLOR" \
    --all \
  ) || cancelled

  if [[ ! -f "$VIDEO" ]]; then
    die "File not found: $VIDEO"
  fi
  success "Video: $VIDEO"
}

collect_youtube() {
  echo ""
  gum style --bold --foreground "$ACCENT_COLOR" \
    "  📺 YouTube URL"
  echo ""

  VIDEO=$(gum input --cursor.foreground "$ACCENT_COLOR" \
    --header "Enter YouTube URL:" \
    --placeholder "https://youtube.com/watch?v=..." \
  ) || cancelled

  if [[ -z "$VIDEO" ]]; then
    die "URL cannot be empty."
  fi
  success "YouTube: $VIDEO"
}

collect_audio_file() {
  echo ""
  gum style --bold --foreground "$ACCENT_COLOR" \
    "  📂 Audio File"
  echo ""

  info "Select an existing audio file to transcribe."
  echo ""

  INPUT_FILE=$(gum file --cursor.foreground "$ACCENT_COLOR" \
    --all \
  ) || cancelled

  if [[ ! -f "$INPUT_FILE" ]]; then
    die "File not found: $INPUT_FILE"
  fi
  success "Audio file: $INPUT_FILE"
}

# ── Screen 4: Confirmation ────────────────────────────────────────

confirm_and_run() {
  echo ""
  gum style --bold --border rounded \
    --border-foreground "$SUCCESS_COLOR" --padding "0 2" \
    "✅ Ready to go"
  echo ""

  # Build summary
  local mode_display="${MODE%% —*}"
  local model_display="$MODEL"
  local topic_display="${TOPIC:-[auto-generated]}"
  local prompt_display=""

  if [[ -n "$PROMPT_FILE" ]]; then
    prompt_display="file: $PROMPT_FILE"
  elif [[ -n "$PROMPT_TEXT" ]]; then
    local preview="${PROMPT_TEXT:0:60}"
    [[ ${#PROMPT_TEXT} -gt 60 ]] && preview="${preview}..."
    prompt_display="inline: \"$preview\""
  else
    prompt_display="[none]"
  fi

  gum style --foreground "$DIM_COLOR" \
    "  Mode:     $mode_display" \
    "  Model:    $model_display" \
    "  Format:   $FORMAT" \
    "  Output:   $OUTPUT_DIR" \
    "  Topic:    $topic_display" \
    "  Prompt:   $prompt_display"

  [[ -n "$VIDEO" ]] && gum style --foreground "$DIM_COLOR" "  Video:    $VIDEO"
  [[ -n "$INPUT_FILE" ]] && gum style --foreground "$DIM_COLOR" "  Audio:    $INPUT_FILE"
  [[ -n "$BRIEFING_FILE" ]] && gum style --foreground "$DIM_COLOR" "  Briefing: $BRIEFING_FILE"
  [[ -n "$HIGH_RES" ]] && gum style --foreground "$DIM_COLOR" "  High-res: ON"
  [[ -n "$GCS_BUCKET" ]] && gum style --foreground "$DIM_COLOR" "  GCS:      $GCS_BUCKET"

  echo ""

  if ! gum confirm "Start recording?"; then
    cancelled
  fi

  echo ""

  # ── Assemble CLI flags ──
  ARGS+=(--output-format "$FORMAT")
  ARGS+=(--model "$MODEL")
  ARGS+=(--output-dir "$OUTPUT_DIR")

  [[ -n "$PROMPT_FILE" ]] && ARGS+=(--prompt-file "$PROMPT_FILE")
  [[ -n "$PROMPT_TEXT" ]] && ARGS+=(--prompt "$PROMPT_TEXT")
  [[ -n "$BRIEFING_FILE" ]] && ARGS+=(--briefing-file "$BRIEFING_FILE")
  [[ -n "$VIDEO" ]] && ARGS+=(--video "$VIDEO")
  [[ -n "$INPUT_FILE" ]] && ARGS+=(--input-file "$INPUT_FILE")
  [[ -n "$HIGH_RES" ]] && ARGS+=(--high-res)
  [[ -n "$NO_VALIDATE" ]] && ARGS+=(--no-validate)
  [[ -n "$GCS_BUCKET" ]] && ARGS+=(--gcs-bucket "$GCS_BUCKET")
  [[ -n "$PROJECT_ID" ]] && ARGS+=(--project-id "$PROJECT_ID")
  [[ -n "$LOCATION" ]] && ARGS+=(--location "$LOCATION")

  # Always use --auto to skip Python-side interactive prompts
  ARGS+=(--auto)

  success "Launching agent-ear-core..."
  echo ""

  exec agent-ear-core "${ARGS[@]}"
}

# ── Main ───────────────────────────────────────────────────────────

main() {
  header
  select_mode
  configure_options

  # Conditional input screens based on mode
  case "$MODE" in
    *"Record Meeting"*)
      collect_meeting_setup
      ;;
    *"With a custom prompt"*)
      collect_prompt
      ;;
    *"Full Agentic"*)
      collect_prompt
      collect_briefing
      ;;
    *"Transcribe Video"*)
      collect_video
      ;;
    *"Transcribe YouTube"*)
      collect_youtube
      ;;
    *"Transcribe File"*)
      collect_audio_file
      ;;
    # "Freeform voice note" — no extra input needed
  esac

  confirm_and_run
}

main "$@"
