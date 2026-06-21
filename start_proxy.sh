#!/bin/bash
# ProxyMCP v2.0 启动脚本 - 使用 AiTun 免注册隧道
#
# 用法:
#   ./start_proxy.sh                    # 免注册模式（自动分配 URL）
#   AITUN_TOKEN=xxx ./start_proxy.sh    # 注册模式（使用 token）
#   AITUN_SUBDOMAIN=myname AITUN_TOKEN=xxx ./start_proxy.sh  # 固定子域名

set -e

echo "🚀 ProxyMCP v2.0 启动脚本 (AiTun)"
echo "=================================="

# 安装 Python 依赖
echo "📦 安装 Python 依赖..."
pip install requests -q 2>/dev/null || pip3 install requests -q

# 安装 aitun-client（如果尚未安装）
if ! command -v aitun >/dev/null 2>&1; then
    echo "⏳ 安装 aitun-client..."
    curl -fsSL https://aitun.cc/install.sh | bash
else
    echo "✅ aitun-client 已安装"
fi

# 显示配置
if [ -n "$AITUN_TOKEN" ]; then
    echo "🔐 注册模式"
    if [ -n "$AITUN_SUBDOMAIN" ]; then
        echo "🏷️  子域名: https://${AITUN_SUBDOMAIN}.t.aitun.cc"
    fi
else
    echo "🆓 免注册模式（自动分配 https://aitun.cc/XXXXXXXX）"
fi

echo ""

# 运行代理服务器
echo "🚀 启动代理服务器..."
python3 proxy_server.py
