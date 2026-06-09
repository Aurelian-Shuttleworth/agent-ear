#!/usr/bin/env bash
# check-gemini-safety.sh — Verify all Gemini generate_content() calls include safety_settings.
#
# Used as a pre-commit hook and CI check. Scans Python files for
# generate_content( calls where a GenerateContentConfig is being constructed
# inline, and ensures safety_settings is included in that config block.
#
# Passthrough calls (where config is a pre-built variable) are not flagged
# because the safety_settings should be set at the config construction site.
#
# Usage: check-gemini-safety.sh file1.py file2.py ...
set -euo pipefail

exit_code=0

for file in "$@"; do
  # Skip non-Python files and test files
  [[ "$file" == *.py ]] || continue
  [[ -f "$file" ]] || continue

  # Find lines with generate_content( — extract line numbers
  while IFS= read -r lineno; do
    # Grab context: the generate_content( call + next 15 lines (typical config block)
    context=$(sed -n "${lineno},$((lineno + 15))p" "$file")

    # Only check calls that construct a GenerateContentConfig inline.
    # Passthrough wrappers (e.g., _call_gemini) receive config as a parameter
    # and are not responsible for setting safety_settings.
    if echo "$context" | grep -q "GenerateContentConfig"; then
      if ! echo "$context" | grep -q "safety_settings"; then
        echo "❌ ${file}:${lineno} — generate_content() with inline config missing safety_settings"
        exit_code=1
      fi
    fi
  done < <(grep -n 'generate_content(' "$file" | cut -d: -f1)
done

if [[ "$exit_code" -eq 0 ]] && [[ "$#" -gt 0 ]]; then
  echo "✅ All generate_content() calls include safety_settings"
fi

exit "$exit_code"
