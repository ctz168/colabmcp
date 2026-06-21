#!/usr/bin/env python3
"""
ColabMCP Client v2.0 - 远程控制 Google Colab / ModelScope 的 Python 客户端

v2.0 新增功能:
- get_status()    — 查看服务器执行状态
- get_history()   — 查看命令历史
- interrupt()     — 中断当前执行（不停止服务器）
- execute_stream() — SSE 流式执行（适合长时间任务）

兼容性:
- 完全兼容 v1.x 服务器（旧端点仍可用）
- v2.0 新端点（/status, /history, /interrupt, /execute_stream）仅在 v2.0 服务器上可用

使用方法:
    # 健康检查
    python colab_client.py --url https://aitun.cc/XXXXXXXX --health

    # 探测环境
    python colab_client.py --url https://aitun.cc/XXXXXXXX --probe

    # 执行代码
    python colab_client.py --url https://aitun.cc/XXXXXXXX -e "print('Hello!')"

    # 执行文件
    python colab_client.py --url https://aitun.cc/XXXXXXXX -f script.py

    # 流式执行（实时输出）
    python colab_client.py --url https://aitun.cc/XXXXXXXX --stream -e "import time; [print(i) or time.sleep(0.5) for i in range(5)]"

    # 中断当前执行
    python colab_client.py --url https://aitun.cc/XXXXXXXX --interrupt

    # 查看状态
    python colab_client.py --url https://aitun.cc/XXXXXXXX --status

    # 查看历史
    python colab_client.py --url https://aitun.cc/XXXXXXXX --history

    # 交互模式
    python colab_client.py --url https://aitun.cc/XXXXXXXX -i
"""

import argparse
import json
import sys
import time
import os
import requests
from typing import Optional, Dict, Any, List, Iterator


class ColabMCPClient:
    """ColabMCP 客户端类"""

    def __init__(self, base_url: str, timeout: int = 600):
        """
        初始化客户端

        Args:
            base_url: ColabMCP 服务器 URL（aitun.cc 或 modelscope.cn 或 ngrok）
            timeout: 默认超时时间（秒）
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'ColabMCP-Client/2.0'
        })

    # ---------- 基本接口 ----------

    def health_check(self) -> Dict[str, Any]:
        """检查服务器健康状态。"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            return {"error": "无法连接到服务器，请检查 URL 是否正确", "status": "connection_failed"}
        except requests.exceptions.Timeout:
            return {"error": "连接超时", "status": "timeout"}
        except Exception as e:
            return {"error": str(e), "status": "failed"}

    def probe_environment(self) -> Dict[str, Any]:
        """探测 Colab 环境（GPU/内存/已安装包）。"""
        try:
            response = self.session.get(f"{self.base_url}/probe", timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def execute_code(self, code: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """执行 Python 代码（变量跨请求持久化）。"""
        try:
            response = self.session.post(
                f"{self.base_url}/execute",
                json={"code": code, "timeout": timeout or self.timeout},
                timeout=(timeout or self.timeout) + 30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            return {"success": False, "error": "执行超时"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def execute_file(self, filepath: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """执行本地 Python 文件。"""
        if not os.path.exists(filepath):
            return {"success": False, "error": f"文件不存在: {filepath}"}
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        return self.execute_code(code, timeout)

    def execute_stream(self, code: str, timeout: Optional[int] = None) -> Iterator[Dict[str, Any]]:
        """
        流式执行 Python 代码（SSE 推送）。

        Yields:
            事件 dict，type 字段为 'status' / 'stdout' / 'stderr' / 'complete' / 'error'
        """
        try:
            with self.session.post(
                f"{self.base_url}/execute_stream",
                json={"code": code, "timeout": timeout or self.timeout},
                stream=True,
                timeout=(timeout or self.timeout) + 30
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    line_str = line.decode('utf-8', errors='replace')
                    if line_str.startswith('data: '):
                        try:
                            yield json.loads(line_str[6:])
                        except json.JSONDecodeError:
                            continue
                    # 忽略 SSE 心跳 ': heartbeat'
        except requests.exceptions.Timeout:
            yield {"type": "error", "content": "流式执行超时"}
        except Exception as e:
            yield {"type": "error", "content": str(e)}

    # ---------- v2.0 新增接口 ----------

    def get_status(self) -> Dict[str, Any]:
        """获取服务器执行状态。"""
        try:
            response = self.session.get(f"{self.base_url}/status", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def get_history(self, limit: int = 20) -> Dict[str, Any]:
        """查看命令历史。"""
        try:
            response = self.session.get(
                f"{self.base_url}/history",
                params={"limit": min(limit, 100)},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def interrupt(self) -> Dict[str, Any]:
        """中断当前执行（不停止服务器）。"""
        try:
            response = self.session.post(f"{self.base_url}/interrupt", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    # ---------- 旧接口（兼容）----------

    def list_variables(self) -> Dict[str, Any]:
        """列出当前运行时变量。"""
        try:
            response = self.session.get(f"{self.base_url}/variables", timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def list_files(self, directory: Optional[str] = None) -> Dict[str, Any]:
        """列出工作目录下的文件。"""
        try:
            params = {"dir": directory} if directory else {}
            response = self.session.get(f"{self.base_url}/files", params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def cleanup(self) -> Dict[str, Any]:
        """清理内存。"""
        try:
            response = self.session.post(f"{self.base_url}/cleanup", timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def test_connection(self) -> bool:
        """测试连接是否正常。"""
        result = self.health_check()
        return result.get("status") == "ok"


# ============== CLI ==============

def print_banner():
    """打印 Banner"""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                    🚀 ColabMCP 客户端 v2.0                    ║
║              远程控制 Google Colab / ModelScope               ║
╚═══════════════════════════════════════════════════════════════╝
""")


def interactive_mode(client: ColabMCPClient):
    """交互式模式"""
    print_banner()
    print("命令:")
    print("  health    - 检查服务器状态")
    print("  probe     - 探测环境 (GPU/内存/包)")
    print("  exec      - 执行代码 (多行输入，空行结束)")
    print("  stream    - 流式执行 (实时输出)")
    print("  run       - 执行文件 (run script.py)")
    print("  vars      - 列出运行时变量")
    print("  files     - 列出工作目录文件")
    print("  status    - 查看执行状态")
    print("  history   - 查看命令历史")
    print("  interrupt - 中断当前执行")
    print("  cleanup   - 清理内存")
    print("  help      - 显示帮助")
    print("  quit      - 退出")
    print("=" * 65 + "\n")

    while True:
        try:
            user_input = input("colab> ").strip()
            if not user_input:
                continue

            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else None

            if cmd in ("quit", "exit", "q"):
                print("👋 再见!")
                break

            elif cmd == "help":
                print("""
命令说明:
  health    - 检查服务器健康状态
  probe     - 探测 Colab 环境（GPU、内存、已安装包）
  exec      - 执行 Python 代码（多行输入，空行结束）
  stream    - 流式执行 Python 代码（实时输出，适合长任务）
  run       - 执行本地 Python 文件 (run script.py)
  vars      - 列出当前运行时存储的变量
  files     - 列出工作目录下的文件
  status    - 查看服务器执行状态（当前目录、是否执行、最近命令）
  history   - 查看命令历史
  interrupt - 中断当前执行（不停止服务器）
  cleanup   - 清理内存和 GPU 缓存
  quit      - 退出客户端
""")

            elif cmd == "health":
                result = client.health_check()
                if "error" in result:
                    print(f"❌ {result['error']}")
                else:
                    print(f"✅ 服务器状态: {result.get('status', 'unknown')}")
                    print(f"   运行时间: {result.get('uptime_minutes', 'N/A')} 分钟")
                    print(f"   可用内存: {result.get('memory_available_gb', 'N/A')} GB")
                    print(f"   GPU 可用: {'是' if result.get('gpu_available') else '否'}")
                    print(f"   当前目录: {result.get('current_directory', 'N/A')}")
                    print(f"   变量数: {result.get('variables_count', 'N/A')}")

            elif cmd == "probe":
                print("🔍 探测环境中...")
                result = client.probe_environment()
                if "error" in result:
                    print(f"❌ {result['error']}")
                else:
                    print(f"\n📊 环境信息:")
                    print(f"   Python: {result.get('python_version', 'N/A')[:60]}...")
                    print(f"   总内存: {result.get('memory_total_gb', 'N/A')} GB")
                    print(f"   可用内存: {result.get('memory_available_gb', 'N/A')} GB")
                    print(f"   已安装包: {result.get('total_packages', 'N/A')} 个")
                    gpu_info = result.get('gpu_info', '')
                    if gpu_info and 'No GPU' not in gpu_info:
                        print(f"\n🎮 GPU 信息:")
                        for line in gpu_info.strip().split('\n')[:5]:
                            print(f"   {line}")
                    else:
                        print(f"\n🎮 GPU: 不可用")

            elif cmd in ("exec", "stream"):
                print("输入 Python 代码 (输入空行结束):")
                code_lines = []
                while True:
                    try:
                        line = input("... ")
                        if not line:
                            break
                        code_lines.append(line)
                    except EOFError:
                        break

                code = "\n".join(code_lines)
                if not code:
                    continue

                if cmd == "exec":
                    print("\n⏳ 执行中...")
                    start = time.time()
                    result = client.execute_code(code)
                    elapsed = time.time() - start

                    if result.get("success"):
                        print(f"✅ 执行成功 ({result.get('execution_time_sec', elapsed):.2f}s)")
                        stdout = result.get("stdout", "")
                        if stdout:
                            print("\n输出:")
                            print(stdout)
                        vars_created = result.get("variables", [])
                        if vars_created:
                            print(f"\n创建的变量: {', '.join(vars_created)}")
                    else:
                        print(f"❌ 执行失败: {result.get('error', 'Unknown error')}")
                        if result.get("traceback"):
                            print("\n错误详情:")
                            print(result["traceback"])
                else:
                    print("\n⏳ 流式执行中（Ctrl+C 中断）...")
                    try:
                        for event in client.execute_stream(code):
                            etype = event.get('type')
                            content = event.get('content', '')
                            if etype == 'stdout':
                                print(content, end='', flush=True)
                            elif etype == 'stderr':
                                print(f"\033[31m{content}\033[0m", end='', flush=True)
                            elif etype == 'status':
                                print(f"\n📌 {content}")
                            elif etype == 'complete':
                                print(f"\n✅ {content}")
                                if event.get('variables'):
                                    print(f"   变量: {', '.join(event['variables'])}")
                            elif etype == 'error':
                                print(f"\n❌ {content}")
                    except KeyboardInterrupt:
                        print("\n\n⏹️  正在请求中断...")
                        r = client.interrupt()
                        print(f"   {r.get('message', '已中断')}")

            elif cmd == "run":
                if not args:
                    print("用法: run <文件路径>")
                    continue
                filepath = args.strip()
                print(f"📄 执行文件: {filepath}")
                result = client.execute_file(filepath)
                if result.get("success"):
                    print(f"✅ 执行成功")
                    if result.get("stdout"):
                        print(result["stdout"])
                else:
                    print(f"❌ 执行失败: {result.get('error', 'Unknown error')}")

            elif cmd == "vars":
                result = client.list_variables()
                if "error" in result:
                    print(f"❌ {result['error']}")
                elif "variables" in result:
                    vars_dict = result["variables"]
                    if vars_dict:
                        print(f"📋 运行时变量 ({result.get('count', len(vars_dict))} 个):")
                        for name, info in vars_dict.items():
                            type_str = info.get("type", "unknown")
                            shape = info.get("shape")
                            length = info.get("length")
                            extra = ""
                            if shape:
                                extra = f", shape: {shape}"
                            elif length:
                                extra = f", len: {length}"
                            print(f"   {name}: {type_str}{extra}")
                    else:
                        print("📋 没有存储的变量")

            elif cmd == "files":
                result = client.list_files()
                if "error" in result:
                    print(f"❌ {result['error']}")
                elif "files" in result:
                    files = result["files"]
                    if files:
                        print(f"📁 文件列表 ({result.get('count', len(files))} 个, 目录: {result.get('directory', '?')}):")
                        for f in sorted(files, key=lambda x: x.get('size_bytes', 0), reverse=True):
                            icon = "📁" if f.get("is_dir") else "📄"
                            print(f"   {icon} {f['name']} ({f.get('size_readable', 'N/A')})")
                    else:
                        print("📁 目录为空")

            elif cmd == "status":
                result = client.get_status()
                if "error" in result:
                    print(f"❌ {result['error']}")
                else:
                    print(f"📊 服务器状态:")
                    print(f"   当前目录: {result.get('current_directory', 'N/A')}")
                    print(f"   是否执行中: {result.get('is_executing', False)}")
                    print(f"   最后命令: {result.get('last_command', 'N/A')[:80]}")
                    print(f"   最后耗时: {result.get('last_execution_time', 0):.3f}s")
                    print(f"   最后错误: {result.get('last_error', '无')}")
                    print(f"   变量数: {result.get('variables_count', 0)}")
                    recent = result.get('recent_history', [])
                    if recent:
                        print(f"\n   最近命令:")
                        for i, c in enumerate(recent, 1):
                            print(f"     {i}. {c[:80]}")

            elif cmd == "history":
                result = client.get_history(limit=20)
                if "error" in result:
                    print(f"❌ {result['error']}")
                else:
                    history = result.get("history", [])
                    print(f"📜 命令历史 (共 {result.get('total', 0)} 条，显示 {len(history)} 条):")
                    for i, h in enumerate(history, 1):
                        status = "✅" if h.get('success') else "❌"
                        cmd_preview = h.get('command', '')[:60]
                        print(f"   [{i}] {status} {h.get('datetime', '?')} | {cmd_preview}")

            elif cmd == "interrupt":
                result = client.interrupt()
                if result.get("success"):
                    print(f"✅ {result.get('message', '已中断')}")
                else:
                    print(f"❌ {result.get('message', '中断失败')}")

            elif cmd == "cleanup":
                result = client.cleanup()
                if result.get("success"):
                    print(f"✅ 内存已清理")
                    print(f"   可用内存: {result.get('memory_available_gb', 'N/A')} GB")
                else:
                    print(f"❌ 清理失败: {result.get('error', 'Unknown error')}")

            else:
                print(f"未知命令: {cmd}。输入 'help' 查看帮助。")

        except KeyboardInterrupt:
            print("\n👋 再见!")
            break
        except Exception as e:
            print(f"错误: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="ColabMCP 客户端 v2.0 - 远程控制 Google Colab / ModelScope",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 健康检查
  python colab_client.py --url https://aitun.cc/XXXXXXXX --health

  # 探测环境
  python colab_client.py --url https://aitun.cc/XXXXXXXX --probe

  # 执行代码
  python colab_client.py --url https://aitun.cc/XXXXXXXX -e "print('Hello!')"

  # 执行文件
  python colab_client.py --url https://aitun.cc/XXXXXXXX -f script.py

  # 流式执行（实时输出）
  python colab_client.py --url https://aitun.cc/XXXXXXXX --stream -e "import time; [print(i) or time.sleep(0.5) for i in range(5)]"

  # 中断当前执行
  python colab_client.py --url https://aitun.cc/XXXXXXXX --interrupt

  # 查看状态
  python colab_client.py --url https://aitun.cc/XXXXXXXX --status

  # 查看历史
  python colab_client.py --url https://aitun.cc/XXXXXXXX --history

  # 交互模式
  python colab_client.py --url https://aitun.cc/XXXXXXXX -i
"""
    )
    parser.add_argument("--url", "-u", required=True, help="ColabMCP 服务器 URL")
    parser.add_argument("--timeout", "-t", type=int, default=600, help="超时时间（秒），默认 600")
    parser.add_argument("--exec", "-e", dest="code", help="要执行的 Python 代码")
    parser.add_argument("--file", "-f", help="要执行的 Python 文件")
    parser.add_argument("--stream", action="store_true", help="流式执行（实时输出）")
    parser.add_argument("--health", action="store_true", help="检查服务器健康状态")
    parser.add_argument("--probe", action="store_true", help="探测环境")
    parser.add_argument("--status", action="store_true", help="查看执行状态")
    parser.add_argument("--history", action="store_true", help="查看命令历史")
    parser.add_argument("--interrupt", action="store_true", help="中断当前执行")
    parser.add_argument("--vars", action="store_true", help="列出运行时变量")
    parser.add_argument("--files", action="store_true", help="列出工作目录文件")
    parser.add_argument("--cleanup", action="store_true", help="清理内存")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互式模式")
    parser.add_argument("--quiet", "-q", action="store_true", help="安静模式，只输出结果")

    args = parser.parse_args()

    client = ColabMCPClient(args.url, args.timeout)

    # 测试连接
    if not args.quiet:
        print("🔍 检查服务器连接...")

    health = client.health_check()
    if "error" in health:
        print(f"❌ {health['error']}")
        print(f"   请确认 URL 正确且服务器正在运行")
        sys.exit(1)

    if not args.quiet:
        print(f"✅ 服务器连接成功!")
        print(f"   版本: {health.get('version', '?')}")
        print(f"   运行时间: {health.get('uptime_minutes', 'N/A')} 分钟")
        print(f"   可用内存: {health.get('memory_available_gb', 'N/A')} GB")
        print()

    # 执行命令
    if args.health:
        print(json.dumps(health, indent=2, ensure_ascii=False))

    elif args.probe:
        result = client.probe_environment()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.status:
        result = client.get_status()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.history:
        result = client.get_history()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.interrupt:
        result = client.interrupt()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.vars:
        result = client.list_variables()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.files:
        result = client.list_files()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.cleanup:
        result = client.cleanup()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.code:
        if args.stream:
            # 流式执行
            try:
                for event in client.execute_stream(args.code):
                    etype = event.get('type')
                    content = event.get('content', '')
                    if etype == 'stdout':
                        print(content, end='', flush=True)
                    elif etype == 'stderr':
                        print(f"\033[31m{content}\033[0m", end='', flush=True)
                    elif etype == 'status':
                        print(f"\n📌 {content}", flush=True)
                    elif etype == 'complete':
                        print(f"\n✅ {content}", flush=True)
                    elif etype == 'error':
                        print(f"\n❌ {content}", flush=True)
            except KeyboardInterrupt:
                print("\n\n⏹️  请求中断...")
                r = client.interrupt()
                print(r.get('message', '已中断'))
        else:
            result = client.execute_code(args.code)
            print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.file:
        if args.stream:
            with open(args.file, 'r', encoding='utf-8') as f:
                code = f.read()
            try:
                for event in client.execute_stream(code):
                    etype = event.get('type')
                    content = event.get('content', '')
                    if etype == 'stdout':
                        print(content, end='', flush=True)
                    elif etype == 'stderr':
                        print(f"\033[31m{content}\033[0m", end='', flush=True)
                    elif etype == 'complete':
                        print(f"\n✅ {content}", flush=True)
                    elif etype == 'error':
                        print(f"\n❌ {content}", flush=True)
            except KeyboardInterrupt:
                print("\n\n⏹️  请求中断...")
                r = client.interrupt()
                print(r.get('message', '已中断'))
        else:
            result = client.execute_file(args.file)
            print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.interactive:
        interactive_mode(client)

    else:
        # 默认进入交互模式
        interactive_mode(client)


if __name__ == "__main__":
    main()
