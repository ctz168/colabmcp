# 🚀 ColabMCP v2.0 - AiTun Free Tunnel Edition

[English](README.md) | [中文](READMecn.md)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ctz168/colabmcp/blob/main/colab_mcp_server_en.ipynb)
[![在 Colab 中打开](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ctz168/colabmcp/blob/main/colab_mcp_server.ipynb)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-2.0.0-green.svg)](https://github.com/ctz168/colabmcp)

Remotely control cloud runtimes (Google Colab, Codespaces, your own server) via an MCP-style HTTP API to execute Python code, leverage GPU resources, and run data analysis — all exposed through a no-sign-up tunnel from [aitun.cc](https://aitun.cc).

## ✨ What's New in v2.0

### Tunnel Upgrade
- 🌐 **Switched to [AiTun](https://aitun.cc)** — replaces ngrok with a no-sign-up tunnel from aitun.cc
- 🆓 **No-registration mode** — zero config by default, auto-assigned public URL like `https://aitun.cc/XXXXXXXX`
- 🏷️ **Optional registered mode** — set token + subdomain to get a fixed subdomain `https://yourname.t.aitun.cc`
- 🛡️ **Tunnel watchdog** — auto-reconnects if the subprocess dies (exponential backoff); restarts the tunnel when the local service stops responding
- 📦 **Auto-install** — aitun-client binary installed via the official install.sh with SHA256 verification

### Stability Improvements
- 🧠 **Single-namespace exec()** — variables persist across requests
- 💾 **Variables saved even on exception** — partial execution results are not lost
- ⏹️ **`/interrupt`** — interrupt the current execution (without stopping the server) by injecting KeyboardInterrupt via ctypes
- 📊 **`/status`** — real-time execution state, current directory, recent commands
- 📜 **`/history`** — view command execution history
- 🌊 **`/execute_stream`** — SSE real-time push of stdout/stderr, ideal for long-running tasks (bots, training)
- 🔇 **Log noise reduction** — werkzeug access logs are completely suppressed, never polluting the SSE stream
- ⏱️ **Longer timeouts** — default 600s, max 1800s
- 💓 **Heartbeat optimization** — no longer requests /health, avoiding lock contention

### API Compatibility
- ✅ Fully backward compatible with v1.x endpoints (`/health`, `/execute`, `/variables`, etc.)
- ✅ v2.0 adds `/status`, `/history`, `/interrupt`, `/execute_stream`

## 🏗️ Architecture

```
┌────────────────┐          ┌───────────────────┐
│   AI Agent     │          │  Cloud Runtime    │
│   (local)      │          │  (Colab/Server)   │
└───────┬────────┘          └─────────┬─────────┘
        │                             │
    HTTP / MCP                    Flask API (app.py)
        │                             │
        │    ┌────────────────────┐    │
        └────┤  AiTun Tunnel      ├────┘
             │  aitun_tunnel.py   │
             │  (auto-reconnect   │
             │   + watchdog)      │
             └────────────────────┘
                      │
                      ▼
              aitun.cc:6639 (public relay)
```

---

## 🚀 Quick Start

### Platform Selection

| Platform | Public URL | Stability | GPU | Recommended For |
|----------|-----------|-----------|-----|-----------------|
| **Google Colab** | AiTun free tunnel | 90 min idle disconnect (Colab limit) | T4 | GPU tasks, quick tests |
| **Local / Codespace** | AiTun free tunnel | Long-running | Depends on hardware | Development & debugging |
| **Your own server** | AiTun free tunnel | Long-running | Depends on hardware | Self-hosted service |

---

## 📦 Google Colab Deployment

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ctz168/colabmcp/blob/main/colab_mcp_server_en.ipynb)  [![在 Colab 中打开](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ctz168/colabmcp/blob/main/colab_mcp_server.ipynb)

> Notebook available in [English](colab_mcp_server_en.ipynb) and [中文](colab_mcp_server.ipynb).

### Steps

1. Click the badge above to open the Colab Notebook
2. Run all cells (**no-registration mode** requires zero configuration)
3. Copy the printed public URL (looks like `https://aitun.cc/XXXXXXXX`)
4. Keep the notebook running

### Optional: Registered Mode (Fixed Subdomain)

Fill in Cell 2:
```python
AITUN_TOKEN = "your aitun.cc token"
AITUN_SUBDOMAIN = "myname"  # gets https://myname.t.aitun.cc
```

Register at [aitun.cc](https://aitun.cc) to get a token.

### Stability Guarantees

- ✅ **Tunnel watchdog**: aitun-client subprocess auto-restarts on crash
- ✅ **Health probe**: every 30s probes local /health; triggers a tunnel reconnect if no response
- ✅ **Exponential backoff**: reconnect interval 3s → 5s → 7s ... → 30s cap
- ✅ **Graceful shutdown**: subprocess is cleaned up when the main process exits

---

## 📁 Project Structure

```
colabmcp/
├── README.md                      # Project documentation (English)
├── READMecn.md                    # 项目文档 (中文)
├── colab_mcp_server_en.ipynb      # Colab one-click startup notebook — English
├── colab_mcp_server.ipynb         # Colab 一键启动 Notebook — 中文
├── app.py                         # Main server v2.0
├── aitun_tunnel.py                # AiTun tunnel watchdog (Colab/Codespace)
├── proxy_server.py                # HTTP proxy service (exposed via AiTun)
├── start_proxy.sh                 # Proxy startup script
├── client/
│   └── colab_client.py            # Python client v2.0
├── examples/
│   └── example_usage.py           # Usage examples
└── LICENSE                        # MIT License
```

---

## 🛠️ API Reference

### Common Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info |
| `/health` | GET | Health check |
| `/probe` | GET | Probe environment (GPU/memory/packages) |
| `/execute` | POST | Execute Python code |
| `/variables` | GET | List runtime variables |
| `/files` | GET | List files |
| `/cleanup` | POST | Clean up memory |

### New in v2.0

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | View execution state (current dir, recent commands) |
| `/history` | GET | View command history (default 20, max 100) |
| `/interrupt` | POST | Interrupt current execution (without stopping server) |
| `/execute_stream` | POST | SSE streaming execution (real-time output) |

---

## 💻 Client Usage

### Install Dependencies

```bash
pip install requests
```

### CLI Usage

```bash
# Health check
python client/colab_client.py --url https://aitun.cc/XXXXXXXX --health

# Probe environment
python client/colab_client.py --url https://aitun.cc/XXXXXXXX --probe

# Execute code (variables persist across requests)
python client/colab_client.py --url https://aitun.cc/XXXXXXXX -e "x = 42"
python client/colab_client.py --url https://aitun.cc/XXXXXXXX -e "print(x * 2)"  # outputs 84

# Execute file
python client/colab_client.py --url https://aitun.cc/XXXXXXXX -f script.py

# Streaming execution (real-time output, ideal for long tasks)
python client/colab_client.py --url https://aitun.cc/XXXXXXXX --stream -e "import time; [print(i) or time.sleep(0.5) for i in range(5)]"

# View execution state
python client/colab_client.py --url https://aitun.cc/XXXXXXXX --status

# View command history
python client/colab_client.py --url https://aitun.cc/XXXXXXXX --history

# Interrupt current execution
python client/colab_client.py --url https://aitun.cc/XXXXXXXX --interrupt

# Interactive mode
python client/colab_client.py --url https://aitun.cc/XXXXXXXX -i
```

### Python API

```python
from colab_client import ColabMCPClient

client = ColabMCPClient("https://aitun.cc/XXXXXXXX")

# Health check
print(client.health_check())

# Execute code (variables persist across requests)
client.execute_code("x = 42")
result = client.execute_code("print(x * 2)")  # outputs 84
print(result["stdout"])

# Streaming execution (ideal for long tasks)
for event in client.execute_stream("import time\nfor i in range(5):\n    print(i)\n    time.sleep(1)"):
    if event["type"] == "stdout":
        print(event["content"], end="")
    elif event["type"] == "complete":
        print(f"\n{event['content']}")

# Interrupt execution (without stopping server)
client.interrupt()

# View status
print(client.get_status())
```

---

## 📝 Usage Examples

### Data Analysis

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

### GPU-Accelerated Computation

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

### Streaming Training (Real-Time Progress)

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

## 🔧 AiTun Tunnel Watchdog (Standalone Use)

`aitun_tunnel.py` can be used standalone to provide a no-sign-up tunnel for any local HTTP service:

```bash
# No-registration mode (auto-assigned URL)
python aitun_tunnel.py -p 8080

# Registered mode (fixed subdomain)
python aitun_tunnel.py -p 8080 -k YOUR_TOKEN --subdomain myname

# Install binary only
python aitun_tunnel.py --install-only
```

As a library:

```python
from aitun_tunnel import AiTunTunnel

tunnel = AiTunTunnel(
    local_port=8080,
    token=None,  # no-registration mode
    no_p2p=True,  # recommended for Colab
    on_url=lambda url: print(f"Public URL: {url}"),
    on_reconnect=lambda n, reason: print(f"Reconnect #{n}: {reason}"),
)
tunnel.start()  # blocking, auto-reconnects
```

Features:
- Auto-installs aitun-client (downloaded from the official aitun.cc)
- Auto-restarts on subprocess exit (exponential backoff, 30s cap)
- Periodically probes the local service; triggers tunnel restart if unresponsive
- Cleans up subprocess on main process exit

---

## ⚠️ Security Notes

| Risk | Description |
|------|-------------|
| 🔴 Code execution | Server can execute arbitrary Python code |
| 🟡 Public exposure | URL is publicly accessible |
| 🟡 No authentication | No built-in auth mechanism |

**Recommendations:**
- Do not share your service URL
- Shut down the service when done
- Do not process sensitive data
- Use a complex subdomain prefix in registered mode

---

## 📋 Platform Limits

| Limit | Google Colab | Local/Codespace | Own Server |
|-------|-------------|-----------------|------------|
| Session length | ~90 min idle | Long-running | Long-running |
| Memory | ~12 GB RAM | Depends on hardware | Depends on hardware |
| GPU | Tesla T4/K80 | Depends on hardware | Depends on hardware |
| Public URL | AiTun free | AiTun free | AiTun free |

---

## 🤝 Contributing

Issues and Pull Requests are welcome!

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgements

- [MCP Protocol](https://spec.modelcontextprotocol.io/) - Model Context Protocol spec
- [Google Colab](https://colab.research.google.com) - Free GPU resources
- [AiTun](https://aitun.cc) - No-sign-up public tunnel service

---

**⭐ If this project helps you, please give it a Star!**
