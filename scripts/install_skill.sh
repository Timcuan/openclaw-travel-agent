#!/usr/bin/env bash
# ============================================================
#  install_skill.sh – Install OpenClaw Travel Skill
#
#  Copies the skill to ~/.openclaw/skills/ so OpenClaw
#  discovers it automatically on next restart.
#
#  Usage:
#    chmod +x scripts/install_skill.sh
#    bash scripts/install_skill.sh
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SKILL_SRC="$PROJECT_DIR/skills/indonesia-travel"
SKILL_DEST="$HOME/.openclaw/skills/indonesia-travel"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   OpenClaw Indonesia Travel Skill Installer  ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${NC}"

# ── 1. Check OpenClaw is installed ────────────────────────────────────────────
if ! command -v openclaw &>/dev/null && [ ! -d "$HOME/.openclaw" ]; then
    echo -e "${YELLOW}⚠️  OpenClaw not found.${NC}"
    echo "   Install OpenClaw first: https://openclaw.ai"
    echo ""
    echo "   Then re-run this script."
    exit 1
fi

# ── 2. Create skill directory ─────────────────────────────────────────────────
echo "📁 Creating skill directory: $SKILL_DEST"
mkdir -p "$SKILL_DEST"

# ── 3. Copy SKILL.md ──────────────────────────────────────────────────────────
echo "📄 Copying SKILL.md..."
cp "$SKILL_SRC/SKILL.md" "$SKILL_DEST/SKILL.md"

# ── 4. Inject API base URL into SKILL.md (if API is running) ─────────────────
API_URL="${OPENCLAW_TRAVEL_API:-http://localhost:8000}"
sed -i.bak "s|http://localhost:8000|$API_URL|g" "$SKILL_DEST/SKILL.md" 2>/dev/null && \
    rm -f "$SKILL_DEST/SKILL.md.bak" || true
echo "   API endpoint: $API_URL"

# ── 5. Verify the API is reachable ────────────────────────────────────────────
echo ""
echo "🔌 Checking API at $API_URL/health ..."
if curl -sf "$API_URL/health" > /dev/null 2>&1; then
    echo -e "   ${GREEN}✅ API is reachable${NC}"
else
    echo -e "   ${YELLOW}⚠️  API not reachable yet. Start it with:${NC}"
    echo "      docker-compose up -d"
    echo "      OR: uvicorn api.main:app --reload"
fi

# ── 6. Also install into workspace/skills if a workspace is active ────────────
WORKSPACE_SKILLS="$PROJECT_DIR/skills"
if [ -d "$WORKSPACE_SKILLS" ]; then
    echo ""
    echo "📦 Skill also available in project at: $WORKSPACE_SKILLS/indonesia-travel/"
fi

# ── 7. Summary ────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}✅ Skill installed successfully!${NC}"
echo ""
echo "   Location : $SKILL_DEST/SKILL.md"
echo "   Triggers : kereta, pesawat, hotel, tiket, travel, perjalanan"
echo ""
echo "   Next steps:"
echo "   1. Restart OpenClaw (or press Cmd+Shift+R to refresh skills)"
echo "   2. Ask OpenClaw: 'cari kereta surabaya jakarta besok'"
echo "   3. OpenClaw will call $API_URL/openclaw/search"
echo ""
echo "   Keep bot running:"
echo "   nohup bash scripts/keep-alive.sh >> logs/bot.log 2>&1 &"
echo ""
