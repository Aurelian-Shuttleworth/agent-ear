#!/usr/bin/env bash
# test-dispatcher.sh — Verify agent-ear.sh routing logic
#
# Tests the dispatcher preamble: --non-interactive flag routing,
# piped stdin detection, and TERM=dumb detection.
#
# Requires: agent-ear.sh path as $1 (or auto-detects from script dir)
# Optional: BASH_PATH env var for Nix sandbox (no /usr/bin/env)

set -euo pipefail

# ── Setup ──────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DISPATCHER="${1:-${SCRIPT_DIR}/agent-ear.sh}"
# In Nix sandbox, /usr/bin/env doesn't exist. Use BASH_PATH if set.
MOCK_BASH="${BASH_PATH:-/bin/sh}"

if [[ ! -f "$DISPATCHER" ]]; then
  echo "❌ Dispatcher not found: $DISPATCHER" >&2
  exit 1
fi

# Create a mock agent-ear-core that prints a sentinel and exits.
# Uses MOCK_BASH for the shebang to work in Nix sandbox (no /usr/bin/env).
MOCK_DIR="$(mktemp -d)"
trap 'rm -rf "$MOCK_DIR"' EXIT

cat > "$MOCK_DIR/agent-ear-core" << MOCK
#!${MOCK_BASH}
echo "ROUTED_TO_CORE"
echo "ARGS=\$*"
exit 0
MOCK
chmod +x "$MOCK_DIR/agent-ear-core"

PASSED=0
FAILED=0

run_test() {
  local name="$1"
  local expected="$2"
  local output="$3"

  if echo "$output" | grep -q "$expected"; then
    echo "  ✅ $name"
    PASSED=$((PASSED + 1))
  else
    echo "  ❌ $name"
    echo "     Expected output to contain: $expected"
    echo "     Got: $output"
    FAILED=$((FAILED + 1))
  fi
}

echo "🧪 Dispatcher routing tests"
echo ""

# ── Test 1: --non-interactive flag routes to core ──────────────────
output=$(PATH="$MOCK_DIR:$PATH" bash "$DISPATCHER" --non-interactive 2>&1 || true)
run_test "--non-interactive flag routes to core" "ROUTED_TO_CORE" "$output"

# ── Test 2: --help flag routes to core ─────────────────────────────
output=$(PATH="$MOCK_DIR:$PATH" bash "$DISPATCHER" --help 2>&1 || true)
run_test "--help flag routes to core" "ROUTED_TO_CORE" "$output"

# ── Test 3: -h flag routes to core ─────────────────────────────────
output=$(PATH="$MOCK_DIR:$PATH" bash "$DISPATCHER" -h 2>&1 || true)
run_test "-h flag routes to core" "ROUTED_TO_CORE" "$output"

# ── Test 4: piped stdin (non-TTY) routes to core ──────────────────
output=$(echo "" | PATH="$MOCK_DIR:$PATH" bash "$DISPATCHER" 2>&1 || true)
run_test "piped stdin (non-TTY) routes to core" "ROUTED_TO_CORE" "$output"

# ── Test 5: TERM=dumb routes to core ──────────────────────────────
output=$(TERM=dumb PATH="$MOCK_DIR:$PATH" bash "$DISPATCHER" 2>&1 || true)
run_test "TERM=dumb routes to core" "ROUTED_TO_CORE" "$output"

# ── Test 6: unset TERM routes to core ─────────────────────────────
output=$(env -u TERM PATH="$MOCK_DIR:$PATH" bash "$DISPATCHER" 2>&1 || true)
run_test "unset TERM routes to core" "ROUTED_TO_CORE" "$output"

# ── Test 7: --non-interactive passes remaining args ────────────────
output=$(PATH="$MOCK_DIR:$PATH" bash "$DISPATCHER" --non-interactive --output-format json 2>&1 || true)
run_test "--non-interactive passes all args through" "ARGS=--non-interactive --output-format json" "$output"

# ── Summary ────────────────────────────────────────────────────────
echo ""
echo "Results: $PASSED passed, $FAILED failed"
[[ "$FAILED" -eq 0 ]]
