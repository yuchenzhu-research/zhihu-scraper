#!/bin/bash
# =============================================================================
# zhihu-scraper 一键安装脚本
# =============================================================================
# 官方安装入口:
#   ./install.sh
#   ./install.sh --recreate
#
# 依赖来源:
#   pyproject.toml (single source of truth)
#
# 会自动完成:
# 1. 检测 Python 3.10+
# 2. 创建本地 .venv
# 3. 用 .venv 里的 python 安装完整依赖
# 4. 安装 Playwright Chromium
# 5. 初始化本地 .local 运行目录与 Cookie 模板
# 6. 运行一次环境检查
# =============================================================================

set -euo pipefail

usage() {
    echo "用法:"
    echo "  ./install.sh            # 复用已有 .venv 并安装/更新依赖"
    echo "  ./install.sh --recreate # 删除并重建 .venv 后重新安装"
}

RECREATE_VENV=false
for arg in "$@"; do
    case "$arg" in
        --recreate)
            RECREATE_VENV=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "❌ 未知参数: $arg"
            usage
            exit 1
            ;;
    esac
done

echo "========================================"
echo "  🕷️ zhihu-scraper 一键安装"
echo "========================================"
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
LOCAL_DIR="$PROJECT_DIR/.local"
COOKIE_FILE="$LOCAL_DIR/cookies.json"
COOKIE_POOL_DIR="$LOCAL_DIR/cookie_pool"

echo "📌 检测 Python 环境..."
if ! command -v python3 >/dev/null 2>&1; then
    echo "   ❌ 未找到 python3，请先安装 Python 3.10+"
    exit 1
fi

PYTHON_BIN="$(command -v python3)"
PYTHON_VER="$("$PYTHON_BIN" --version)"
echo "   ✅ $PYTHON_VER ($PYTHON_BIN)"

cd "$PROJECT_DIR"

echo ""
echo "📌 配置虚拟环境..."
if [ "$RECREATE_VENV" = true ] && [ -d "$VENV_DIR" ]; then
    echo "   🗑️  按要求重建 .venv ..."
    rm -rf "$VENV_DIR"
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "   🔧 创建 .venv ..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    echo "   ✅ 已创建"
else
    echo "   ✅ 复用已有 .venv"
fi

VENV_PYTHON="$VENV_DIR/bin/python"

echo ""
echo "📌 升级打包工具..."
"$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel

echo ""
echo "📌 安装项目依赖 (from pyproject.toml)..."
"$VENV_PYTHON" -m pip install -e ".[full]"
echo "   ✅ 完整依赖安装完成"

echo ""
echo "📌 安装 Playwright Chromium..."
"$VENV_PYTHON" -m playwright install chromium
echo "   ✅ Playwright Chromium 已安装"

echo ""
echo "📌 初始化本地运行目录..."
mkdir -p "$LOCAL_DIR" "$COOKIE_POOL_DIR"
echo "   ✅ 已准备 .local/ 与 .local/cookie_pool/"

echo ""
echo "📌 检查本地 Cookie 模板..."
if [ ! -f "$COOKIE_FILE" ] && [ -f "cookies.example.json" ]; then
    cp "cookies.example.json" "$COOKIE_FILE"
    echo "   ✅ 已从 cookies.example.json 创建 .local/cookies.json"
fi

if [ ! -f "$COOKIE_FILE" ] && [ -f "cookies.json" ]; then
    echo "   ℹ️  检测到历史路径 cookies.json，当前版本仍兼容，但建议后续迁移到 .local/cookies.json"
fi

if [ ! -f "$COOKIE_FILE" ] && [ ! -f "cookies.json" ]; then
    echo "   ⚠️  未找到 .local/cookies.json"
    echo "   💡 可先游客模式运行，但推荐补上 z_c0 / d_c0"
elif [ -f "$COOKIE_FILE" ] && grep -q "YOUR_Z_C0_HERE" "$COOKIE_FILE"; then
    echo "   ⚠️  .local/cookies.json 仍是占位符，请填入你自己的 z_c0 / d_c0"
elif [ -f "$COOKIE_FILE" ]; then
    echo "   ✅ .local/cookies.json 已配置"
elif grep -q "YOUR_Z_C0_HERE" cookies.json; then
    echo "   ⚠️  cookies.json 仍是占位符，请填入你自己的 z_c0 / d_c0"
else
    echo "   ✅ cookies.json 已配置"
fi

echo ""
echo "📌 运行环境检查..."
"$VENV_PYTHON" cli/app.py check || true

echo ""
echo "========================================"
echo -e "  ${GREEN}✅ 安装完成${NC}"
echo "========================================"
echo ""
echo "推荐直接运行:"
echo ""
echo "  ./zhihu manual"
echo "  ./zhihu check"
echo "  ./zhihu interactive"
echo ""
echo "如果你习惯显式使用 Python:"
echo ""
echo "  .venv/bin/python cli/app.py manual"
echo "  .venv/bin/python cli/app.py fetch \"https://www.zhihu.com/question/28696373/answer/2835848212\""
echo ""
echo "说明:"
echo "  - 依赖由 pyproject.toml 统一声明"
echo "  - install.sh 是官方一键安装入口"
echo "  - 如需一键重建环境: ./install.sh --recreate"
echo "  - 根目录 ./zhihu 会优先使用本地 .venv"
echo "  - 本地凭据、日志等运行文件建议统一放在 .local/"
echo ""
echo "========================================"
