# 🚀 ColabMCP v2.0 - AiTun 免注册隧道版

[English](README.md) | [中文](READMecn.md)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ctz168/colabmcp/blob/main/colab_mcp_server.ipynb)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-2.0.0-green.svg)](https://github.com/ctz168/colabmcp)

通过 MCP 风格的 HTTP API，让 AI Agent 远程控制云端运行时（Google Colab、Codespace、自有服务器等），执行 Python 代码、利用 GPU 资源、进行数据分析 — 全部通过 [aitun.cc](https://aitun.cc) 的免注册隧道暴露到公网。

## ✨ v2.0 更新

### 隧道升级
- 🌐 **切换到 [AiTun](https://aitun.cc)** — 替代 ngrok，使用 aitun.cc 免注册隧道
- 🆓 **免注册模式** — 默认零配置，自动分配 `https://aitun.cc/XXXXXXXX` 公网 URL
- 🏷️ **可选注册模式** — 设置 token + subdomain 获取固定子域名 `https://yourname.t.aitun.cc`
- 🛡️ **隧道守护器** — 子进程退出后自动重连（指数退避）；本地服务无响应时自动重启隧道
- 📦 **自动安装** — aitun-client 二进制通过官方 install.sh 安装，带 SHA256 校验

### 稳定性增强
- 🧠 **单一命名空间 exec()** — 变量跨请求持久化
- 💾 **异常时仍保存变量** — 部分执行结果不丢失
- ⏹️ **`/interrupt`** — 中断当前执行（不停止服务器），通过 ctypes 注入 KeyboardInterrupt
- 📊 **`/status`** — 实时查看执行状态、当前目录、最近命令
- 📜 **`/history`** — 查看命令执行历史
- 🌊 **`/execute_stream`** — SSE 实时推送 stdout/stderr，适合长时间任务（Bot/训练）
- 🔇 **日志降噪** — werkzeug 访问日志完全屏蔽，不会污染 SSE 流
- ⏱️ **超时延长** — 默认 600s，最大 1800s
- 💓 **心跳优化** — 不再请求 /health，避免与执行锁冲突

### API 兼容性
- ✅ 完全向后兼容 v1.x 的端点（`/health`、`/execute`、`/variables` 等）
- ✅ v2.0 新增 `/status`、`/history`、`/interrupt`、`/execute_stream`

## 🏗️ 架构

```
┌────────────────┐          ┌───────────────────┐
│   AI Agent     │          │   云端运行时       │
│   (本地)       │          │ (Colab/服务器)     │
└───────┬────────┘          └─────────┬─────────┘
        │                             │
    HTTP / MCP                    Flask API (app.py)
        │                             │
        │    ┌────────────────────┐    │
        └────┤  AiTun 隧道 (HTTPS) ├────┘
             │  aitun_tunnel.py   │
             │  (自动重连+看门狗)  │
             └────────────────────┘
                      │
                      ▼
              aitun.cc:6639 (公网中继)
```

---

## 🚀 快速开始

### 平台选择

| 平台 | 公网 URL | 稳定性 | GPU | 推荐场景 |
|------|---------|--------|-----|---------|
| **Google Colab** | AiTun 免注册隧道 | 90分钟断开（Colab 限制） | T4 | GPU 任务、临时测试 |
| **本地 / Codespace** | AiTun 免注册隧道 | 长期运行 | 取决于硬件 | 开发调试 |
| **自有服务器** | AiTun 免注册隧道 | 长期运行 | 取决于硬件 | 自托管服务 |

---

## 📦 Google Colab 部署

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ctz168/colabmcp/blob/main/colab_mcp_server.ipynb)

### 步骤

1. 点击上方按钮打开 Colab Notebook
2. 运行所有 cells（**免注册模式**无需任何配置）
3. 复制输出的公网 URL（形如 `https://aitun.cc/XXXXXXXX`）
4. 保持 notebook 运行

### 可选：注册模式（固定子域名）

在 Cell 2 中填入：
```python
AITUN_TOKEN = "你的 aitun.cc token"
AITUN_SUBDOMAIN = "myname"  # 获得 https://myname.t.aitun.cc
```

前往 [aitun.cc](https://aitun.cc) 注册并获取 token。

### 稳定性保障

- ✅ **隧道守护器**：aitun-client 子进程崩溃后自动重启
- ✅ **健康探测**：每 30s 探测本地 /health，无响应时触发隧道重连
- ✅ **指数退避**：重连间隔 3s → 5s → 7s ... → 30s 上限
- ✅ **优雅退出**：主进程退出时自动清理子进程

---

## 📁 项目结构

```
colabmcp/
├── README.md                      # 项目文档 (英文)
├── READMecn.md                    # 项目文档 (中文)
├── colab_mcp_server.ipynb         # Colab 一键启动 Notebook (AiTun 隧道)
├── app.py                         # 服务器主程序 v2.0
├── aitun_tunnel.py                # AiTun 隧道守护器 (Colab/Codespace 用)
├── proxy_server.py                # HTTP 代理服务 (通过 AiTun 暴露)
├── start_proxy.sh                 # 代理启动脚本
├── client/
│   └── colab_client.py            # Python 客户端 v2.0
├── examples/
│   └── example_usage.py           # 使用示例
└── LICENSE                        # MIT 许可证
```

---

## 🛠️ API 接口

### 通用端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 服务信息 |
| `/health` | GET | 健康检查 |
| `/probe` | GET | 探测环境（GPU/内存/包） |
| `/execute` | POST | 执行 Python 代码 |
| `/variables` | GET | 列出运行时变量 |
| `/files` | GET | 列出文件 |
| `/cleanup` | POST | 清理内存 |

### v2.0 新增端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/status` | GET | 查看执行状态（当前目录、最近命令） |
| `/history` | GET | 查看命令历史（默认 20 条，最多 100） |
| `/interrupt` | POST | 中断当前执行（不停止服务器） |
| `/execute_stream` | POST | SSE 流式执行（实时输出） |

---

## 💻 客户端使用

### 安装依赖

```bash
pip install requests
```

### 命令行使用

```bash
# 健康检查
python client/colab_client.py --url https://aitun.cc/XXXXXXXX --health

# 探测环境
python client/colab_client.py --url https://aitun.cc/XXXXXXXX --probe

# 执行代码（变量跨请求持久化）
python client/colab_client.py --url https://aitun.cc/XXXXXXXX -e "x = 42"
python client/colab_client.py --url https://aitun.cc/XXXXXXXX -e "print(x * 2)"  # 输出 84

# 执行文件
python client/colab_client.py --url https://aitun.cc/XXXXXXXX -f script.py

# 流式执行（实时输出，适合长时间任务）
python client/colab_client.py --url https://aitun.cc/XXXXXXXX --stream -e "import time; [print(i) or time.sleep(0.5) for i in range(5)]"

# 查看执行状态
python client/colab_client.py --url https://aitun.cc/XXXXXXXX --status

# 查看命令历史
python client/colab_client.py --url https://aitun.cc/XXXXXXXX --history

# 中断当前执行
python client/colab_client.py --url https://aitun.cc/XXXXXXXX --interrupt

# 交互模式
python client/colab_client.py --url https://aitun.cc/XXXXXXXX -i
```

### Python 代码调用

```python
from colab_client import ColabMCPClient

client = ColabMCPClient("https://aitun.cc/XXXXXXXX")

# 健康检查
print(client.health_check())

# 执行代码（变量跨请求持久化）
client.execute_code("x = 42")
result = client.execute_code("print(x * 2)")  # 输出 84
print(result["stdout"])

# 流式执行（适合长时间任务）
for event in client.execute_stream("import time\nfor i in range(5):\n    print(i)\n    time.sleep(1)"):
    if event["type"] == "stdout":
        print(event["content"], end="")
    elif event["type"] == "complete":
        print(f"\n{event['content']}")

# 中断执行（不停止服务器）
client.interrupt()

# 查看状态
print(client.get_status())
```

---

## 📝 使用示例

### 数据分析

```python
code = """
import pandas as pd
import numpy as np

df = pd.DataFrame({
    'A': np.random.randn(1000),
    'B': np.random.randn(1000),
})
print(df.describe())
"""
result = client.execute_code(code)
```

### GPU 加速计算

```python
code = """
import torch

print(f"CUDA: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    x = torch.randn(5000, 5000, device='cuda')
    y = torch.randn(5000, 5000, device='cuda')
    z = torch.matmul(x, y)
    print(f"Result shape: {z.shape}")
"""
result = client.execute_code(code)
```

### 流式训练（实时查看进度）

```python
code = """
import time
for epoch in range(10):
    loss = 1.0 / (epoch + 1)
    print(f"Epoch {epoch}: loss={loss:.4f}")
    time.sleep(0.5)
"""
for event in client.execute_stream(code):
    if event["type"] == "stdout":
        print(event["content"], end="")
```

---

## 🔧 AiTun 隧道守护器（独立使用）

`aitun_tunnel.py` 可以独立使用，为任何本地 HTTP 服务提供免注册隧道：

```bash
# 免注册模式（自动分配 URL）
python aitun_tunnel.py -p 8080

# 注册模式（固定子域名）
python aitun_tunnel.py -p 8080 -k YOUR_TOKEN --subdomain myname

# 仅安装二进制
python aitun_tunnel.py --install-only
```

作为库使用：

```python
from aitun_tunnel import AiTunTunnel

tunnel = AiTunTunnel(
    local_port=8080,
    token=None,  # 免注册模式
    no_p2p=True,  # Colab 推荐关闭 P2P
    on_url=lambda url: print(f"公网 URL: {url}"),
    on_reconnect=lambda n, reason: print(f"重连 #{n}: {reason}"),
)
tunnel.start()  # 阻塞，自动重连
```

特性：
- 自动安装 aitun-client（来自 aitun.cc 官方下载）
- 子进程退出后自动重启（指数退避，上限 30s）
- 周期性探测本地服务，无响应时触发隧道重启
- 主进程退出时优雅清理子进程

---

## ⚠️ 安全注意事项

| 风险 | 说明 |
|------|------|
| 🔴 代码执行 | 服务器可执行任意 Python 代码 |
| 🟡 公网暴露 | URL 公开可访问 |
| 🟡 无认证 | 没有身份验证机制 |

**建议措施：**
- 不要分享你的服务 URL
- 使用完毕后关闭服务
- 不要处理敏感数据
- 注册模式下使用复杂子域名前缀

---

## 📋 平台限制

| 限制 | Google Colab | 本地/Codespace | 自有服务器 |
|------|-------------|----------------|------------|
| 会话时长 | ~90 分钟无活动 | 长期运行 | 长期运行 |
| 内存 | ~12 GB RAM | 取决于硬件 | 取决于硬件 |
| GPU | Tesla T4/K80 | 取决于硬件 | 取决于硬件 |
| 公网 URL | AiTun 免注册 | AiTun 免注册 | AiTun 免注册 |

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [MCP Protocol](https://spec.modelcontextprotocol.io/) - Model Context Protocol 规范
- [Google Colab](https://colab.research.google.com) - 免费 GPU 资源
- [AiTun](https://aitun.cc) - 免注册公网隧道服务

---

**⭐ 如果这个项目对你有帮助，请给一个 Star！**
