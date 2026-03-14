#!/bin/bash
# ProxyMCP 启动脚本 - GitHub Codespace 版本

echo "🚀 ProxyMCP 启动脚本"
echo "===================="

# 检查 ngrok token
if [ -z "$NGROK_AUTH_TOKEN" ]; then
    echo "⚠️ 请设置 NGROK_AUTH_TOKEN 环境变量"
    echo "获取 token: https://dashboard.ngrok.com/get-started/your-authtoken"
    echo ""
    echo "设置方法:"
    echo "  export NGROK_AUTH_TOKEN=your_token_here"
    echo ""
    read -p "或者输入你的 token: " token
    export NGROK_AUTH_TOKEN=$token
fi

# 安装依赖
echo "📦 安装依赖..."
pip install pyngrok requests -q

# 运行代理服务器
echo "🚀 启动代理服务器..."
python3 proxy_server.py
