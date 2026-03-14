# 🚀 ColabMCP - AI Agent 远程控制 Google Colab / ModelScope

通过 MCP (Model Context Protocol) 协议，让 AI Agent 远程控制云端运行时，执行 Python 代码、利用 GPU 资源、进行数据分析。

## ✨ 特性

- 🔗 **一键启动** - 点击按钮即可在云端启动 MCP 服务器
- 🤖 **AI Agent 集成** - 支持 Claude、GPT 等 AI Agent 远程调用
- 🎮 **交互式客户端** - 提供命令行工具直接操作
- 💾 **GPU 支持** - 自动检测并利用云端 GPU 资源
- 📊 **环境探测** - 查询内存、GPU、已安装包等信息
- 🧹 **内存管理** - 支持清理内存和 GPU 缓存
- 🛡️ **错误隔离** - 代码出错不会导致服务崩溃

## 🏗️ 架构

```
┌────────────────┐          ┌───────────────────┐
│   AI Agent     │          │   云端运行时       │
│   (本地)       │          │ (Colab/ModelScope) │
└───────┬────────┘          └─────────┬─────────┘
        │                             │
    HTTP / MCP                    Flask API
        │                             │
        └─────────────────────────────┘
              公网 URL (ngrok/自动)
```

---

## 🚀 快速开始

### 平台选择

| 平台 | 公网 URL | 稳定性 | GPU | 推荐场景 |
|------|---------|--------|-----|---------|
| **Google Colab** | 需要 ngrok | 90分钟断开 | T4 | 临时测试、GPU 任务 |
| **ModelScope** | ✅ 自动提供 | 长期运行 | xGPU | 稳定服务、长期开发 |

---

## 📦 Google Colab 部署

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ctz168/colabmcp/blob/main/colab_mcp_server.ipynb)

### 步骤

1. 点击上方按钮打开 Colab Notebook
2. 设置你的 ngrok token（[免费获取](https://dashboard.ngrok.com/get-started/your-authtoken)）
3. 运行所有 cells
4. 复制输出的公网 URL
5. 保持 notebook 运行

### 注意事项

- 需要 ngrok 账户获取公网 URL
- 90 分钟无活动会断开
- 每次重启 URL 会变化

---

## 📦 ModelScope 部署

### 步骤

1. 登录 [ModelScope](https://modelscope.cn)
2. 创建「创空间」
3. 上传 `modelscope_mcp_server.ipynb` 或复制代码
4. 运行所有 cells
5. 获取自动生成的公网 URL（格式：`https://your-space.modelscope.cn`）

### 优势

- ✅ **无需 ngrok** - 自动提供公网 URL
- ✅ **更稳定** - 不会 90 分钟断开
- ✅ **端口固定** - 7860 端口
- ✅ **免费资源** - 2vCPU / 16GB RAM

### ModelScope 创空间配置

创建创空间时选择：
- **SDK**: Gradio（或自定义）
- **资源**: 免费 CPU（2vCPU/16GB）
- **端口**: 7860（固定）

---

## 📁 项目结构

```
colabmcp/
├── README.md                      # 项目文档
├── colab_mcp_server.ipynb         # Colab 一键启动 Notebook
├── modelscope_mcp_server.ipynb    # ModelScope 一键启动 Notebook
├── client/
│   └── colab_client.py            # Python 客户端
├── examples/
│   └── example_usage.py           # 使用示例
└── LICENSE                        # MIT 许可证
```

---

## 🛠️ API 接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 服务信息 |
| `/health` | GET | 健康检查 |
| `/probe` | GET | 探测环境（GPU/内存/包） |
| `/execute` | POST | 执行 Python 代码 |
| `/variables` | GET | 列出运行时变量 |
| `/files` | GET | 列出文件 |
| `/cleanup` | POST | 清理内存 |

---

## 💻 客户端使用

### 安装依赖

```bash
pip install requests
```

### 命令行使用

```bash
# 健康检查
python client/colab_client.py --url https://your-url.modelscope.cn --health

# 探测环境
python client/colab_client.py --url https://your-url.modelscope.cn --probe

# 执行代码
python client/colab_client.py --url https://your-url.modelscope.cn -e "print('Hello!')"

# 执行文件
python client/colab_client.py --url https://your-url.modelscope.cn -f script.py

# 交互模式
python client/colab_client.py --url https://your-url.modelscope.cn -i
```

### Python 代码调用

```python
import requests

# Colab 或 ModelScope URL
url = "https://your-url.modelscope.cn"

# 健康检查
health = requests.get(f"{url}/health").json()
print(health)

# 执行代码
result = requests.post(f"{url}/execute", json={
    "code": "print('Hello from cloud!')"
})
print(result.json())
```

### 执行 Shell 命令

```python
import requests

url = "https://your-url.modelscope.cn"

# 安装包
result = requests.post(f"{url}/execute", json={
    "code": "import subprocess; subprocess.run(['pip', 'install', 'torch'], check=True)"
})

# 克隆仓库
result = requests.post(f"{url}/execute", json={
    "code": "import subprocess; subprocess.run(['git', 'clone', 'https://github.com/xxx/repo.git'], check=True)"
})
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
result = requests.post(f"{url}/execute", json={"code": code})
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
result = requests.post(f"{url}/execute", json={"code": code})
```

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

---

## 📋 平台限制

| 限制 | Google Colab | ModelScope |
|------|-------------|------------|
| 会话时长 | ~90 分钟无活动 | 长期运行 |
| 内存 | ~12 GB RAM | ~16 GB RAM |
| GPU | Tesla T4/K80 | xGPU（申请） |
| 公网 URL | ngrok（每次变化） | 固定 URL |

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [MCP Protocol](https://spec.modelcontextprotocol.io/) - Model Context Protocol 规范
- [Google Colab](https://colab.research.google.com) - 免费 GPU 资源
- [ModelScope](https://modelscope.cn) - 魔搭社区免费资源
- [ngrok](https://ngrok.com) - 内网穿透工具

---

**⭐ 如果这个项目对你有帮助，请给一个 Star！**
