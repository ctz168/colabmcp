# ProxyMCP - GitHub Codespace 代理服务

在 GitHub Codespace 中运行代理服务，通过 ngrok 暴露公网地址。

## 🚀 快速开始

### 方法一：一键启动（推荐）

1. 创建 GitHub Codespace
2. 在终端运行：

```bash
# 下载并运行
curl -fsSL https://raw.githubusercontent.com/ctz168/colabmcp/main/proxy_server.py -o proxy_server.py
export NGROK_AUTH_TOKEN=your_token_here
pip install pyngrok requests -q
python3 proxy_server.py
```

### 方法二：克隆仓库

```bash
git clone https://github.com/ctz168/colabmcp.git
cd colabmcp
export NGROK_AUTH_TOKEN=your_token_here
chmod +x start_proxy.sh
./start_proxy.sh
```

## 📋 获取 ngrok Token

1. 访问 https://dashboard.ngrok.com/get-started/your-authtoken
2. 注册/登录
3. 复制你的 token

## 🔧 使用方法

启动后会显示代理地址，例如：
```
🔗 代理地址: https://xxxx.ngrok-free.app
```

### 方法一：Python 使用

```python
import requests

proxy_url = "https://xxxx.ngrok-free.app"
proxies = {
    'http': proxy_url,
    'https': proxy_url
}

# 使用代理请求
response = requests.get('https://api.ipify.org?format=json', proxies=proxies)
print(f"代理 IP: {response.json()['ip']}")
```

### 方法二：curl 使用

```bash
# HTTP 请求
curl -x https://xxxx.ngrok-free.app https://api.ipify.org

# HTTPS 请求
curl -x https://xxxx.ngrok-free.app https://httpbin.org/ip
```

### 方法三：浏览器设置

1. 打开浏览器代理设置
2. 设置 HTTP/HTTPS 代理：
   - 地址: `xxxx.ngrok-free.app`（去掉 https://）
   - 端口: `443`

## ⚠️ 注意事项

1. **免费版 ngrok 限制**：
   - 每分钟 40 个连接
   - 每分钟 20 个请求
   - URL 每次启动会变化

2. **安全提醒**：
   - 不要分享你的代理地址
   - 不要用于敏感操作

3. **Codespace 限制**：
   - 免费版每月 60 小时
   - 闲置 30 分钟会休眠

## 📊 支持的功能

| 功能 | 支持 |
|------|------|
| HTTP 代理 | ✅ |
| HTTPS 代理 | ✅ (CONNECT 方法) |
| 认证 | ❌ (待添加) |
| SOCKS5 | ❌ (待添加) |

## 🔗 相关链接

- [ngrok 官网](https://ngrok.com)
- [GitHub Codespace](https://github.com/features/codespaces)
