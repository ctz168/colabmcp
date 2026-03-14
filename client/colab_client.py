#!/usr/bin/env python3
"""
ColabMCP Client - 远程控制 Google Colab 的 Python 客户端

使用方法:
    # 健康检查
    python colab_client.py --url https://your-url.ngrok-free.app --health
    
    # 探测环境
    python colab_client.py --url https://your-url.ngrok-free.app --probe
    
    # 执行代码
    python colab_client.py --url https://your-url.ngrok-free.app -e "print('Hello!')"
    
    # 交互模式
    python colab_client.py --url https://your-url.ngrok-free.app -i
"""

import argparse
import json
import sys
import time
import os
import requests
from typing import Optional, Dict, Any, List


class ColabMCPClient:
    """ColabMCP 客户端类"""
    
    def __init__(self, base_url: str, timeout: int = 300):
        """
        初始化客户端
        
        Args:
            base_url: Colab 服务器的 ngrok URL
            timeout: 默认超时时间（秒）
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'ColabMCP-Client/1.0'
        })
    
    def health_check(self) -> Dict[str, Any]:
        """
        检查服务器健康状态
        
        Returns:
            包含服务器状态信息的字典
        """
        try:
            response = self.session.get(
                f"{self.base_url}/health",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            return {"error": "无法连接到服务器，请检查 URL 是否正确", "status": "connection_failed"}
        except requests.exceptions.Timeout:
            return {"error": "连接超时", "status": "timeout"}
        except Exception as e:
            return {"error": str(e), "status": "failed"}
    
    def probe_environment(self) -> Dict[str, Any]:
        """
        探测 Colab 环境
        
        Returns:
            包含 GPU、内存、已安装包等信息的字典
        """
        try:
            response = self.session.get(
                f"{self.base_url}/probe",
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def execute_code(self, code: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        执行 Python 代码
        
        Args:
            code: 要执行的 Python 代码
            timeout: 超时时间（秒），默认使用初始化时的值
        
        Returns:
            执行结果，包含 success、stdout、error 等字段
        """
        try:
            response = self.session.post(
                f"{self.base_url}/execute",
                json={
                    "code": code,
                    "timeout": timeout or self.timeout
                },
                timeout=(timeout or self.timeout) + 30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            return {"success": False, "error": "执行超时"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def execute_file(self, filepath: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        执行 Python 文件
        
        Args:
            filepath: Python 文件路径
            timeout: 超时时间
        
        Returns:
            执行结果
        """
        if not os.path.exists(filepath):
            return {"success": False, "error": f"文件不存在: {filepath}"}
        
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        
        return self.execute_code(code, timeout)
    
    def list_variables(self) -> Dict[str, Any]:
        """
        列出当前运行时变量
        
        Returns:
            变量信息字典
        """
        try:
            response = self.session.get(
                f"{self.base_url}/variables",
                timeout=15
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def list_files(self) -> Dict[str, Any]:
        """
        列出 Colab /content 目录下的文件
        
        Returns:
            文件列表
        """
        try:
            response = self.session.get(
                f"{self.base_url}/files",
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def cleanup(self) -> Dict[str, Any]:
        """
        清理内存
        
        Returns:
            清理结果
        """
        try:
            response = self.session.post(
                f"{self.base_url}/cleanup",
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def test_connection(self) -> bool:
        """
        测试连接是否正常
        
        Returns:
            True 如果连接正常
        """
        result = self.health_check()
        return result.get("status") == "ok"


def print_banner():
    """打印 Banner"""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                    🚀 ColabMCP 客户端                         ║
║              远程控制 Google Colab 运行时                      ║
╚═══════════════════════════════════════════════════════════════╝
""")


def interactive_mode(client: ColabMCPClient):
    """交互式模式"""
    print_banner()
    print("命令:")
    print("  health    - 检查服务器状态")
    print("  probe     - 探测环境 (GPU/内存/包)")
    print("  exec      - 执行代码 (多行输入，空行结束)")
    print("  run       - 执行文件 (run script.py)")
    print("  vars      - 列出运行时变量")
    print("  files     - 列出 Colab 文件")
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
  run       - 执行本地 Python 文件 (run script.py)
  vars      - 列出当前运行时存储的变量
  files     - 列出 Colab /content 目录下的文件
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
            
            elif cmd == "exec":
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
                if code:
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
                        print(f"📁 Colab 文件 ({result.get('count', len(files))} 个):")
                        for f in sorted(files, key=lambda x: x.get('size_bytes', 0), reverse=True):
                            icon = "📁" if f.get("is_dir") else "📄"
                            print(f"   {icon} {f['name']} ({f.get('size_readable', 'N/A')})")
                    else:
                        print("📁 /content 目录为空")
            
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
        description="ColabMCP 客户端 - 远程控制 Google Colab",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 健康检查
  python colab_client.py --url https://xxx.ngrok-free.app --health
  
  # 探测环境
  python colab_client.py --url https://xxx.ngrok-free.app --probe
  
  # 执行代码
  python colab_client.py --url https://xxx.ngrok-free.app -e "print('Hello!')"
  
  # 执行文件
  python colab_client.py --url https://xxx.ngrok-free.app -f script.py
  
  # 交互模式
  python colab_client.py --url https://xxx.ngrok-free.app -i
"""
    )
    parser.add_argument("--url", "-u", required=True, help="Colab 服务器的 ngrok URL")
    parser.add_argument("--timeout", "-t", type=int, default=300, help="超时时间（秒），默认 300")
    parser.add_argument("--exec", "-e", dest="code", help="要执行的 Python 代码")
    parser.add_argument("--file", "-f", help="要执行的 Python 文件")
    parser.add_argument("--health", action="store_true", help="检查服务器健康状态")
    parser.add_argument("--probe", action="store_true", help="探测 Colab 环境")
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
        print(f"   请确认 URL 正确且 Colab notebook 正在运行")
        sys.exit(1)
    
    if not args.quiet:
        print(f"✅ 服务器连接成功!")
        print(f"   运行时间: {health.get('uptime_minutes', 'N/A')} 分钟")
        print(f"   可用内存: {health.get('memory_available_gb', 'N/A')} GB")
        print()
    
    # 执行命令
    if args.health:
        print(json.dumps(health, indent=2, ensure_ascii=False))
    
    elif args.probe:
        result = client.probe_environment()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.code:
        result = client.execute_code(args.code)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.file:
        result = client.execute_file(args.file)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.interactive:
        interactive_mode(client)
    
    else:
        # 默认进入交互模式
        interactive_mode(client)


if __name__ == "__main__":
    main()
