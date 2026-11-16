#!/bin/bash
# Install uncomment from the polylint Homebrew tap and smoke-test it.
# Set TAP_DIR to a local checkout of polylint/homebrew-tap to test an unpublished formula.

set -euo pipefail

tap="polylint/tap"

echo "Testing Homebrew formula..."

if brew tap | grep -qx "$tap"; then
  brew untap "$tap"
fi
if [ -n "${TAP_DIR:-}" ]; then
  echo "Tapping $tap from local checkout $TAP_DIR..."
  brew tap "$tap" "$TAP_DIR"
else
  brew tap "$tap"
fi

echo "Installing uncomment from $tap..."
brew install --verbose "$tap/uncomment"

echo "Testing uncomment command..."
uncomment --version

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cat >"$tmp/test_uncomment.py" <<'EOF'
# This is a comment
def hello():
    print("Hello, world!")  # Inline comment
    # Another comment
    return True
EOF

echo "Running uncomment on test file..."
uncomment --dry-run "$tmp/test_uncomment.py"

echo "Homebrew formula test completed successfully."

echo "Cleaning up..."
brew uninstall uncomment
brew untap "$tap"
