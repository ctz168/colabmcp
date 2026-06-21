#!/usr/bin/env python3
"""
ProxyMCP v2.0 - 通过 AiTun 暴露的 HTTP 代理服务

在 GitHub Codespace / 任何 Linux 环境中运行，创建一个可通过 aitun.cc 访问的 HTTP 代理。

相对 v1.x 改进：
- 用 aitun.cc 免注册隧道替代 ngrok（无需 token，零配置）
- 集成 aitun_tunnel.AiTunTunnel 守护器（自动重连、健康探测）
- 本地服务无响应时自动重启隧道

使用方法:
1. 安装依赖: pip install requests
2. 运行: python proxy_server.py
3. 使用输出的 URL 作为 HTTP 代理
"""

import os
import sys
import socket
import threading
import select
import time
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

# 将当前目录加入 sys.path，便于导入 aitun_tunnel
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from aitun_tunnel import AiTunTunnel, install_aitun, find_aitun_binary
except ImportError:
    # aitun_tunnel.py 同目录不存在时，提示用户
    print("❌ 找不到 aitun_tunnel.py，请从仓库根目录运行：")
    print("   python proxy_server.py")
    sys.exit(1)


# ============== 配置 ==============
PROXY_PORT = int(os.environ.get('PROXY_PORT', '8888'))
# 留空使用免注册模式；填入你的 aitun.cc token 启用子域名模式
AITUN_TOKEN = os.environ.get('AITUN_TOKEN', '')
AITUN_SUBDOMAIN = os.environ.get('AITUN_SUBDOMAIN', '')
AITUN_SERVER = os.environ.get('AITUN_SERVER', 'aitun.cc:6639')


# ============== HTTP 代理服务器 ==============

class ProxyHandler(BaseHTTPRequestHandler):
    """HTTP 代理处理器"""

    def log_message(self, format, *args):
        print(f"[代理] {self.address_string()} - {format % args}")

    def do_CONNECT(self):
        """处理 HTTPS 连接 (CONNECT 方法)"""
        try:
            host, port = self.path.split(':')
            port = int(port)

            target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target_socket.settimeout(30)
            target_socket.connect((host, port))

            self.send_response(200, 'Connection Established')
            self.end_headers()

            self._tunnel(self.connection, target_socket)

        except Exception as e:
            print(f"[错误] CONNECT 失败: {e}")
            self.send_error(500, str(e))

    def do_GET(self):
        self._handle_http_request()

    def do_POST(self):
        self._handle_http_request()

    def do_PUT(self):
        self._handle_http_request()

    def do_DELETE(self):
        self._handle_http_request()

    def _handle_http_request(self):
        try:
            import urllib.request

            url = self.path
            if not url.startswith('http'):
                url = 'http://' + self.headers['Host'] + self.path

            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else None

            headers = dict(self.headers)
            headers.pop('Proxy-Connection', None)
            headers.pop('Proxy-Authorization', None)

            req = urllib.request.Request(
                url, data=body, headers=headers, method=self.command
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                self.send_response(response.status)
                for key, value in response.headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(response.read())

        except Exception as e:
            print(f"[错误] 请求失败: {e}")
            self.send_error(500, str(e))

    def _tunnel(self, client_socket, target_socket):
        """双向隧道转发"""
        client_socket.setblocking(0)
        target_socket.setblocking(0)

        sockets = [client_socket, target_socket]
        timeout = 60
        last_activity = time.time()

        while True:
            if time.time() - last_activity > timeout:
                break

            try:
                readable, _, exceptional = select.select(sockets, [], sockets, 1)
            except Exception:
                break

            if exceptional:
                break

            if readable:
                last_activity = time.time()

                for sock in readable:
                    try:
                        data = sock.recv(65536)
                        if not data:
                            return
                        if sock is client_socket:
                            target_socket.sendall(data)
                        else:
                            client_socket.sendall(data)
                    except Exception:
                        return

        target_socket.close()


class ThreadedHTTPServer(HTTPServer):
    """多线程 HTTP 服务器"""
    allow_reuse_address = True

    def process_request(self, request, client_address):
        thread = threading.Thread(
            target=self.process_request_thread,
            args=(request, client_address)
        )
        thread.daemon = True
        thread.start()

    def process_request_thread(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)


def main():
    print("=" * 60)
    print("🚀 ProxyMCP v2.0 - AiTun 代理服务器")
    print("=" * 60)
    print()

    # 确保 aitun-client 已安装
    if not find_aitun_binary():
        print("⏳ 安装 aitun-client...")
        install_aitun()

    # 启动 HTTP 代理服务器（后台线程）
    print(f"📡 启动本地 HTTP 代理 (port={PROXY_PORT})...")
    server = ThreadedHTTPServer(('0.0.0.0', PROXY_PORT), ProxyHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)
    print(f"✅ 本地代理已启动: 0.0.0.0:{PROXY_PORT}")

    # 启动 AiTun 隧道（阻塞）
    def on_url(public_url):
        print()
        print("=" * 60)
        print("🎉 代理服务已启动!")
        print("=" * 60)
        print()
        print(f"🔗 代理地址: {public_url}")
        print()
        print("📋 使用方法:")
        print("-" * 60)
        print()
        print("方法一：浏览器设置")
        host = public_url.replace('https://', '').replace('http://', '').split('/')[0]
        print(f"  HTTP 代理: {host}")
        print(f"  端口: 443 (HTTPS) 或 80 (HTTP)")
        print()
        print("方法二：Python 代码")
        print(f"""
import requests

proxies = {{
    'http': '{public_url}',
    'https': '{public_url}'
}}

response = requests.get('https://api.ipify.org?format=json', proxies=proxies)
print(response.json())
""")
        print("方法三：curl 命令")
        print(f"  curl -x {public_url} https://api.ipify.org")
        print()
        print("-" * 60)
        print()
        print("⚠️  按 Ctrl+C 停止服务")
        print("=" * 60)

    tunnel = AiTunTunnel(
        local_port=PROXY_PORT,
        token=AITUN_TOKEN or None,
        subdomain=AITUN_SUBDOMAIN or None,
        server=AITUN_SERVER,
        no_p2p=False,  # Codespace 可启用 P2P
        verbose=True,
        on_url=on_url,
    )

    try:
        tunnel.start(block=True)
    except KeyboardInterrupt:
        print("\n\n👋 服务已停止")
    finally:
        tunnel.stop()
        server.shutdown()


if __name__ == '__main__':
    main()
