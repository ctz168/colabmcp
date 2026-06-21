# ProxyMCP v2.0 - AiTun 免注册代理服务

在 GitHub Codespace 或任何 Linux 环境中运行 HTTP 代理服务，通过 [aitun.cc](https://aitun.cc) 免注册隧道暴露公网地址。

## 🚀 快速开始

### 方法一：一键启动（推荐）

1. 创建 GitHub Codespace
2. 在终端运行：

```bash
# 下载并运行
curl -fsSL https://raw.githubusercontent.com/ctz168/colabmcp/main/proxy_server.py -o proxy_server.py
curl -fsSL https://raw.githubusercontent.com/ctz168/colabmcp/main/aitun_tunnel.py -o aitun_tunnel.py
pip install requests -q
python3 proxy_server.py
```

### 方法二：克隆仓库

```bash
git clone https://github.com/ctz168/colabmcp.git
cd colabmcp
chmod +x start_proxy.sh
./start_proxy.sh
```

## 🔧 配置（可选）

默认为免注册模式，自动分配 `https://aitun.cc/XXXXXXXX` 公网 URL。

如需固定子域名，设置环境变量：

```bash
export AITUN_TOKEN=your_aitun_cc_token
export AITUN_SUBDOMAIN=myname  # 可选，获得 https://myname.t.aitun.cc
./start_proxy.sh
```

前往 [aitun.cc](https://aitun.cc) 注册并获取 token。

## 📋 使用方法

启动后会显示代理地址，例如：
```
🔗 代理地址: https://aitun.cc/XXXXXXXX
```

### 方法一：Python 使用

```python
import requests

proxy_url = "https://aitun.cc/XXXXXXXX"
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
curl -x https://aitun.cc/XXXXXXXX https://api.ipify.org

# HTTPS 请求
curl -x https://aitun.cc/XXXXXXXX https://httpbin.org/ip
```

### 方法三：浏览器设置

1. 打开浏览器代理设置
2. 设置 HTTP/HTTPS 代理：
   - 地址: `aitun.cc`（去掉 https://）
   - 端口: `443`

## ⚠️ 注意事项

1. **免注册模式限制**：
   - URL 每次启动都会变化
   - 隧道 24 小时后过期（重新启动即可）

2. **稳定性保障**：
   - 隧道子进程崩溃后自动重连
   - 本地代理无响应时自动重启隧道
   - 指数退避重连（3s → 30s 上限）

3. **安全提醒**：
   - 不要分享你的代理地址
   - 不要用于敏感操作

## 📊 支持的功能

| 功能 | 支持 |
|------|------|
| HTTP 代理 | ✅ |
| HTTPS 代理 | ✅ (CONNECT 方法) |
| 自动重连 | ✅ |
| 固定子域名 | ✅（注册模式） |
| 认证 | ❌ (待添加) |
| SOCKS5 | ❌ (待添加) |

## 🔗 相关链接

- [AiTun 官网](https://aitun.cc)
- [GitHub Codespace](https://github.com/features/codespaces)
