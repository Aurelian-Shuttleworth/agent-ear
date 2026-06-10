#!/usr/bin/env bash
# shellcheck shell=bash
# agent-ear — Smart dispatcher & Gum TUI wrapper
#
# This is the main entry point. It first checks for non-interactive
# usage (e.g. --non-interactive or piped input) and delegates directly to the Python core.
# If interactive, it launches the TUI wizard to guide the user.

set -euo pipefail

# ── Early exit: agent/non-interactive paths ──
for arg in "$@"; do
  case "$arg" in
    --non-interactive|--help|-h) exec agent-ear-core "$@" ;;
  esac
done

# Not a real interactive terminal → skip TUI, go straight to core.
# Checks: stdin not a TTY (piped/cron/agent), stdout not a TTY (captured),
# or TERM is dumb/unset (CI runners, editors, agent sandboxes).
if [[ ! -t 0 ]] || [[ ! -t 1 ]] || [[ -z "${TERM:-}" ]] || [[ "${TERM:-}" == "dumb" ]]; then
  exec agent-ear-core "$@"
fi

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
PROMPT_LABEL=""
VIDEO=""
INPUT_FILE=""
HIGH_RES=""
GCS_BUCKET=""
PROJECT_ID=""
LOCATION=""
NO_VALIDATE=""

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

# ── Template Engine ────────────────────────────────────────────────
# Templates are .md files with YAML frontmatter (name, icon, description)
# and a prompt body. The AGENT_EAR_TEMPLATES_DIR env var points to the
# templates directory (set by the Nix wrapper).

TEMPLATES_DIR="${AGENT_EAR_TEMPLATES_DIR:-}"

# Parse YAML frontmatter fields from a template file.
# Sets globals: TMPL_NAME, TMPL_ICON
parse_template_frontmatter() {
  local file="$1"
  TMPL_NAME=""
  TMPL_ICON=""
  local in_frontmatter=false
  while IFS= read -r line; do
    if [[ "$line" == "---" ]]; then
      if $in_frontmatter; then break; fi
      in_frontmatter=true
      continue
    fi
    if $in_frontmatter; then
      case "$line" in
        name:*)  TMPL_NAME="${line#name: }" ;;
        icon:*)  TMPL_ICON="${line#icon: }" ;;
      esac
    fi
  done < "$file"
}

# Extract prompt body (everything after the closing --- frontmatter delimiter).
read_template_body() {
  local file="$1"
  local found_start=false
  local found_end=false
  while IFS= read -r line; do
    if [[ "$line" == "---" ]]; then
      if ! $found_start; then
        found_start=true
        continue
      elif ! $found_end; then
        found_end=true
        continue
      fi
    fi
    if $found_end; then
      echo "$line"
    fi
  done < "$file"
}

# Load a user-facing template by filename from templates/
load_template() {
  local filename="$1"
  local path="${TEMPLATES_DIR}/${filename}"
  if [[ ! -f "$path" ]]; then
    die "Template not found: $filename"
  fi
  parse_template_frontmatter "$path"
  PROMPT_TEXT=$(read_template_body "$path")
  PROMPT_LABEL="${TMPL_ICON} ${TMPL_NAME}"
  NO_VALIDATE="true"  # Curated templates skip prompt validation
}

# Load an internal template (auto-applied, not user-selectable)
load_internal_template() {
  local filename="$1"
  local path="${TEMPLATES_DIR}/internal/${filename}"
  if [[ ! -f "$path" ]]; then
    die "Internal template not found: $filename"
  fi
  parse_template_frontmatter "$path"
  PROMPT_TEXT=$(read_template_body "$path")
  PROMPT_LABEL="${TMPL_ICON} ${TMPL_NAME}"
  NO_VALIDATE="true"  # Curated templates skip prompt validation
}

# ── Screen 1: Mode Selection (two-tier) ───────────────────────────

select_mode() {
  gum style --bold --foreground "$ACCENT_COLOR" \
    "  What would you like to do?"
  echo ""

  local top_choice
  top_choice=$(gum choose --cursor.foreground "$ACCENT_COLOR" \
    "🎤 Record Now — Start recording immediately" \
    "📝 Custom Prompt — Write or load your own prompt" \
    "📋 Templates ▸ — Choose a premade prompt template" \
    "🎬 Transcribe ▸ — Video, YouTube, or audio file" \
    "❌ Cancel" \
  ) || cancelled

  [[ "$top_choice" == "❌ Cancel" ]] && cancelled

  case "$top_choice" in
    *"Record Now"*)
      MODE="🎤 Record Now"
      load_template "quick-transcript.md"
      ;;
    *"Custom Prompt"*)
      MODE="📝 Custom Prompt"
      ;;
    *"Templates"*)
      select_template
      ;;
    *"Transcribe"*)
      select_transcribe_source
      ;;
  esac

  echo ""
  success "Mode: ${MODE}"
}

select_template() {
  echo ""
  gum style --bold --foreground "$ACCENT_COLOR" \
    "  📋 Choose a template"
  echo ""

  if [[ -z "$TEMPLATES_DIR" ]] || [[ ! -d "$TEMPLATES_DIR" ]]; then
    die "Templates directory not found. Is AGENT_EAR_TEMPLATES_DIR set?"
  fi

  # Scan templates dir for .md files (top-level only, not internal/)
  local -a labels=()
  local -a files=()
  for f in "${TEMPLATES_DIR}"/*.md; do
    [[ -f "$f" ]] || continue
    parse_template_frontmatter "$f"
    labels+=("${TMPL_ICON} ${TMPL_NAME}")
    files+=("$(basename "$f")")
  done

  if [[ ${#labels[@]} -eq 0 ]]; then
    die "No templates found in $TEMPLATES_DIR"
  fi

  labels+=("↩️  Back")

  local choice
  choice=$(printf '%s\n' "${labels[@]}" | \
    gum choose --cursor.foreground "$ACCENT_COLOR") || cancelled

  [[ "$choice" == "↩️  Back" ]] && select_mode && return

  # Find which file was selected
  for i in "${!labels[@]}"; do
    if [[ "${labels[$i]}" == "$choice" ]]; then
      load_template "${files[$i]}"
      MODE="📋 ${TMPL_NAME}"
      return
    fi
  done
}

select_transcribe_source() {
  echo ""
  gum style --bold --foreground "$ACCENT_COLOR" \
    "  🎬 Choose a source to transcribe"
  echo ""

  local choice
  choice=$(gum choose --cursor.foreground "$ACCENT_COLOR" \
    "🎬 Transcribe Video — Local file" \
    "📺 Transcribe YouTube — From URL" \
    "📂 Transcribe File — Existing audio file" \
    "↩️  Back" \
  ) || cancelled

  [[ "$choice" == "↩️  Back" ]] && select_mode && return

  case "$choice" in
    *"Transcribe Video"*)
      MODE="🎬 Transcribe Video"
      load_internal_template "video-transcription.md"
      ;;
    *"Transcribe YouTube"*)
      MODE="📺 Transcribe YouTube"
      load_internal_template "youtube-transcription.md"
      ;;
    *"Transcribe File"*)
      MODE="📂 Transcribe File"
      load_internal_template "audio-transcription.md"
      ;;
  esac
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
    PROMPT_LABEL="inline (${#PROMPT_TEXT} chars)"
    success "Prompt: $PROMPT_LABEL"
  else
    info "Select a prompt file..."
    PROMPT_FILE=$(gum file --cursor.foreground "$ACCENT_COLOR" \
      --all \
    ) || cancelled

    if [[ ! -f "$PROMPT_FILE" ]]; then
      die "File not found: $PROMPT_FILE"
    fi
    PROMPT_LABEL="file: $(basename "$PROMPT_FILE")"
    success "Prompt: $PROMPT_LABEL"
  fi
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
  local model_display="$MODEL"
  local topic_display="${TOPIC:-[auto-generated]}"
  local prompt_display=""

  if [[ -n "$PROMPT_LABEL" ]]; then
    prompt_display="$PROMPT_LABEL"
  elif [[ -n "$PROMPT_FILE" ]]; then
    prompt_display="file: $PROMPT_FILE"
  elif [[ -n "$PROMPT_TEXT" ]]; then
    local preview="${PROMPT_TEXT:0:60}"
    [[ ${#PROMPT_TEXT} -gt 60 ]] && preview="${preview}..."
    prompt_display="inline: \"$preview\""
  else
    prompt_display="[none]"
  fi

  gum style --foreground "$DIM_COLOR" \
    "  Mode:     $MODE" \
    "  Model:    $model_display" \
    "  Format:   $FORMAT" \
    "  Output:   $OUTPUT_DIR" \
    "  Topic:    $topic_display" \
    "  Prompt:   $prompt_display"

  [[ -n "$VIDEO" ]] && gum style --foreground "$DIM_COLOR" "  Video:    $VIDEO"
  [[ -n "$INPUT_FILE" ]] && gum style --foreground "$DIM_COLOR" "  Audio:    $INPUT_FILE"
  [[ -n "$HIGH_RES" ]] && gum style --foreground "$DIM_COLOR" "  High-res: ON"
  [[ -n "$GCS_BUCKET" ]] && gum style --foreground "$DIM_COLOR" "  GCS:      $GCS_BUCKET"

  echo ""

  # Confirmation with optional prompt preview
  local confirm_choice
  confirm_choice=$(gum choose --cursor.foreground "$ACCENT_COLOR" \
    "✅ Start" \
    "🔍 View prompt" \
    "❌ Cancel" \
  ) || cancelled

  case "$confirm_choice" in
    *"View prompt"*)
      echo ""
      if [[ -n "$PROMPT_TEXT" ]]; then
        echo "$PROMPT_TEXT" | gum pager --border rounded \
          --border-foreground "$DIM_COLOR"
      elif [[ -n "$PROMPT_FILE" ]]; then
        gum pager --border rounded \
          --border-foreground "$DIM_COLOR" < "$PROMPT_FILE"
      else
        info "No prompt to display."
      fi
      echo ""
      # Re-show confirmation after viewing
      confirm_and_run
      return
      ;;
    *"Cancel"*)
      cancelled
      ;;
  esac

  echo ""

  # ── Assemble CLI flags ──
  ARGS+=(--output-format "$FORMAT")
  ARGS+=(--model "$MODEL")
  ARGS+=(--output-dir "$OUTPUT_DIR")

  [[ -n "$PROMPT_FILE" ]] && ARGS+=(--prompt-file "$PROMPT_FILE")
  [[ -n "$PROMPT_TEXT" ]] && ARGS+=(--prompt "$PROMPT_TEXT")
  [[ -n "$VIDEO" ]] && ARGS+=(--video "$VIDEO")
  [[ -n "$INPUT_FILE" ]] && ARGS+=(--input-file "$INPUT_FILE")
  [[ -n "$HIGH_RES" ]] && ARGS+=(--high-res)
  [[ -n "$NO_VALIDATE" ]] && ARGS+=(--no-validate)
  [[ -n "$GCS_BUCKET" ]] && ARGS+=(--gcs-bucket "$GCS_BUCKET")
  [[ -n "$PROJECT_ID" ]] && ARGS+=(--project-id "$PROJECT_ID")
  [[ -n "$LOCATION" ]] && ARGS+=(--location "$LOCATION")

  # Always use --non-interactive to skip Python-side interactive prompts
  ARGS+=(--non-interactive)

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
    *"Custom Prompt"*)
      collect_prompt
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
    # Record Now and Templates — prompt already loaded, no extra input
  esac

  confirm_and_run
}

main "$@"
