#!/usr/bin/env bash
# waimao_toolkit_new installer
# Usage: bash install.sh [--target-dir DIR] [--skip-chromium]
#   --target-dir      Target skills directory (default: .claude/skills)
#                     e.g. .openode/skills, .opencode/skills
#   --skip-chromium   Skip Playwright Chromium browser download (~150MB)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR=".claude/skills"
SKIP_CHROMIUM=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-dir)
      TARGET_DIR="$2"
      shift 2
      ;;
    --skip-chromium)
      SKIP_CHROMIUM=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: bash install.sh [--target-dir DIR] [--skip-chromium]"
      exit 1
      ;;
  esac
done

# Determine absolute target path (relative to CWD)
TARGET_ABS="$(cd "$(pwd)" && mkdir -p "$TARGET_DIR" && cd "$TARGET_DIR" && pwd)"

echo "=== Waimao Toolkit Installer ==="
echo "Source:  $SCRIPT_DIR/skills/"
echo "Target:  $TARGET_ABS/"
echo ""

# Create target directory
mkdir -p "$TARGET_ABS"

# Copy skills (rsync-style: skip excluded items)
SKILLS=(_shared company-profile customer-acquisition email-craft email-blast)

for skill in "${SKILLS[@]}"; do
  src="$SCRIPT_DIR/skills/$skill"
  dst="$TARGET_ABS/$skill"

  if [[ ! -d "$src" ]]; then
    echo "WARNING: $skill not found in source, skipping"
    continue
  fi

  echo "Copying $skill ..."

  # Use tar to copy, excluding unwanted files/dirs
  if command -v rsync &>/dev/null; then
    rsync -a \
      --exclude='__pycache__/' \
      --exclude='.agents/' \
      --exclude='*.pyc' \
      --exclude='profile.json' \
      --exclude='profile.md' \
      --exclude='sources/' \
      --exclude='output/' \
      --exclude='*.csv' \
      --exclude='config.json' \
      --exclude='skills-lock.json' \
      "$src/" "$dst/"
  else
    # Fallback: use tar with exclude
    mkdir -p "$dst"
    tar cf - \
      --exclude='__pycache__' \
      --exclude='.agents' \
      --exclude='*.pyc' \
      --exclude='profile.json' \
      --exclude='profile.md' \
      --exclude='sources' \
      --exclude='output' \
      --exclude='*.csv' \
      --exclude='config.json' \
      --exclude='skills-lock.json' \
      -C "$src" . | tar xf - -C "$dst"
  fi
done

# Replace __SKILL_DIR__ placeholder in all SKILL.md files
echo ""
echo "Replacing path placeholders ..."

find "$TARGET_ABS" -name "SKILL.md" -print0 | while IFS= read -r -d '' f; do
  if grep -q '__SKILL_DIR__' "$f"; then
    # Use the parent of the skills dir as the target
    sed -i "s|__SKILL_DIR__|$TARGET_ABS|g" "$f"
    echo "  Updated: $(basename "$(dirname "$f")")/SKILL.md"
  fi
done

# -------------------------------------------------------
# Step 3: Install dependencies
# -------------------------------------------------------
check_and_install_deps() {
  echo ""
  echo "=== Checking Dependencies ==="

  # --- Step 1: Check toolchain ---
  PYTHON_CMD=""
  if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
  elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
  else
    echo "ERROR: Python not found. Please install Python 3.8+ first."
    exit 1
  fi

  PIP_CMD=""
  if command -v pip3 &>/dev/null; then
    PIP_CMD="pip3"
  elif command -v pip &>/dev/null; then
    PIP_CMD="pip"
  else
    echo "ERROR: pip not found. Please install pip first."
    exit 1
  fi

  if ! command -v node &>/dev/null; then
    echo "ERROR: Node.js not found. Please install Node.js first."
    exit 1
  fi

  if ! command -v npm &>/dev/null; then
    echo "ERROR: npm not found. Please install npm first."
    exit 1
  fi

  echo "  Python: $PYTHON_CMD ($("$PYTHON_CMD" --version 2>&1))"
  echo "  pip:    $PIP_CMD"
  echo "  Node:   $(node --version 2>&1)"
  echo "  npm:    $(npm --version 2>&1)"

  # --- Step 2: Install missing Python packages ---
  echo ""
  echo "Checking Python packages ..."

  # pip_name:import_name pairs
  declare -A PKG_MAP=(
    [requests]=requests
    [beautifulsoup4]=bs4
    [python-dotenv]=dotenv
    [replicate]=replicate
    [playwright]=playwright
  )

  for pip_pkg in "${!PKG_MAP[@]}"; do
    import_name="${PKG_MAP[$pip_pkg]}"
    if "$PYTHON_CMD" -c "import $import_name" 2>/dev/null; then
      echo "  [OK] $pip_pkg"
    else
      echo "  [Installing] $pip_pkg ..."
      if "$PIP_CMD" install "$pip_pkg" --quiet; then
        echo "  [OK] $pip_pkg (installed)"
      else
        echo "  [WARN] Failed to install $pip_pkg"
      fi
    fi
  done

  # --- Step 3: Playwright Chromium browser ---
  if [[ "$SKIP_CHROMIUM" == true ]]; then
    echo ""
    echo "Skipping Chromium browser (--skip-chromium)."
  else
    echo ""
    echo "Checking Playwright Chromium browser ..."
    # Check if chromium is already installed
    if "$PYTHON_CMD" -c "
from playwright.sync_api import sync_playwright
try:
    with sync_playwright() as p:
        b = p.chromium.executable_path
        import os
        print('exists' if os.path.exists(b) else 'missing')
except Exception:
    print('missing')
" 2>/dev/null | grep -q "exists"; then
      echo "  [OK] Chromium browser already installed"
    else
      echo "  [Installing] Playwright Chromium (~150MB) ..."
      "$PYTHON_CMD" -m playwright install chromium
      echo "  [OK] Chromium browser installed"
    fi
  fi

  # --- Step 4: lark-cli (optional) ---
  echo ""
  echo "Checking lark-cli (optional) ..."
  if npx lark-cli --version &>/dev/null 2>&1; then
    echo "  [OK] lark-cli available via npx"
  else
    echo "  [SKIP] lark-cli not found."
    echo "         If you need Feishu/Lark spreadsheet support,"
    echo "         install it with: npm install -g @larksuite/cli"
  fi

  echo ""
  echo "=== Dependencies Ready ==="
}

check_and_install_deps

# Copy .env.example to project root if .env doesn't exist
ENV_FILE="$(pwd)/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -f "$SCRIPT_DIR/.env.example" ]]; then
    cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
    echo ""
    echo "Created .env file. Please fill in your API keys:"
    echo "  $ENV_FILE"
  fi
else
  echo ""
  echo ".env already exists, skipping creation."
fi

echo ""
echo "=== Installation Complete ==="
echo "Skills installed to: $TARGET_ABS"
echo ""
echo "Next steps:"
echo "  1. Edit .env and add your API keys"
echo "  2. Restart your AI agent to load the new skills"
echo ""
