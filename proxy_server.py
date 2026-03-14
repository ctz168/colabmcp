#!/usr/bin/env python3
"""
ProxyMCP - 通过 ngrok 暴露的代理服务

在 GitHub Codespace 中运行，创建一个可通过 ngrok 访问的 HTTP 代理。

使用方法:
1. 安装依赖: pip install pyngrok requests
2. 设置 ngrok token: ngrok authtoken YOUR_TOKEN
3. 运行: python proxy_server.py
4. 使用输出的 URL 作为 HTTP 代理
"""

import os
import sys
import socket
import threading
import select
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess

# ============== 配置 ==============
PROXY_PORT = 8888
NGROK_REGION = "ap"  # 亚太地区，延迟更低

# ============== HTTP 代理服务器 ==============

class ProxyHandler(BaseHTTPRequestHandler):
    """HTTP 代理处理器"""
    
    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[代理] {self.address_string()} - {format % args}")
    
    def do_CONNECT(self):
        """处理 HTTPS 连接 (CONNECT 方法)"""
        try:
            # 解析目标地址
            host, port = self.path.split(':')
            port = int(port)
            
            # 连接目标服务器
            target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target_socket.settimeout(30)
            target_socket.connect((host, port))
            
            # 发送 200 响应
            self.send_response(200, 'Connection Established')
            self.end_headers()
            
            # 双向转发数据
            self._tunnel(self.connection, target_socket)
            
        except Exception as e:
            print(f"[错误] CONNECT 失败: {e}")
            self.send_error(500, str(e))
    
    def do_GET(self):
        """处理 HTTP GET 请求"""
        self._handle_http_request()
    
    def do_POST(self):
        """处理 HTTP POST 请求"""
        self._handle_http_request()
    
    def do_PUT(self):
        """处理 HTTP PUT 请求"""
        self._handle_http_request()
    
    def do_DELETE(self):
        """处理 HTTP DELETE 请求"""
        self._handle_http_request()
    
    def _handle_http_request(self):
        """处理普通 HTTP 请求"""
        try:
            import urllib.request
            
            # 构建目标 URL
            url = self.path
            if not url.startswith('http'):
                url = 'http://' + self.headers['Host'] + self.path
            
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else None
            
            # 构建请求
            headers = dict(self.headers)
            # 移除代理相关头部
            headers.pop('Proxy-Connection', None)
            headers.pop('Proxy-Authorization', None)
            
            req = urllib.request.Request(
                url,
                data=body,
                headers=headers,
                method=self.command
            )
            
            # 发送请求
            with urllib.request.urlopen(req, timeout=30) as response:
                # 发送响应
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
            # 检查超时
            if time.time() - last_activity > timeout:
                break
            
            # 等待数据
            try:
                readable, _, exceptional = select.select(sockets, [], sockets, 1)
            except:
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
                        
                        # 转发到另一端
                        if sock is client_socket:
                            target_socket.sendall(data)
                        else:
                            client_socket.sendall(data)
                    except:
                        return
        
        target_socket.close()


class ThreadedHTTPServer(HTTPServer):
    """多线程 HTTP 服务器"""
    allow_reuse_address = True
    
    def process_request(self, request, client_address):
        """在新线程中处理请求"""
        thread = threading.Thread(target=self.process_request_thread,
                                  args=(request, client_address))
        thread.daemon = True
        thread.start()
    
    def process_request_thread(self, request, client_address):
        """处理请求的线程函数"""
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)


def start_ngrok(port):
    """启动 ngrok 隧道"""
    try:
        from pyngrok import ngrok
    except ImportError:
        print("正在安装 pyngrok...")
        subprocess.run(['pip', 'install', 'pyngrok', '-q'], check=True)
        from pyngrok import ngrok
    
    # 清理旧连接
    try:
        ngrok.kill()
    except:
        pass
    
    time.sleep(1)
    
    # 启动 ngrok
    try:
        tunnel = ngrok.connect(port, region=NGROK_REGION)
        return tunnel.public_url
    except Exception as e:
        print(f"ngrok 启动失败: {e}")
        return None


def main():
    print("=" * 60)
    print("🚀 ProxyMCP - 代理服务器")
    print("=" * 60)
    print()
    
    # 检查 ngrok token
    ngrok_token = os.environ.get('NGROK_AUTH_TOKEN', '')
    if ngrok_token:
        print(f"✅ 检测到 ngrok token")
        subprocess.run(['ngrok', 'authtoken', ngrok_token], capture_output=True)
    
    # 启动 ngrok
    print(f"📡 正在启动 ngrok (端口 {PROXY_PORT})...")
    public_url = start_ngrok(PROXY_PORT)
    
    if public_url:
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
        print(f"  HTTP 代理: {public_url.replace('https://', '').replace('http://', '')}")
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
        print("⚠️ 按 Ctrl+C 停止服务")
        print("=" * 60)
    else:
        print("❌ ngrok 启动失败，请检查 token 是否正确")
        print("获取 token: https://dashboard.ngrok.com/get-started/your-authtoken")
        return
    
    # 启动代理服务器
    try:
        server = ThreadedHTTPServer(('0.0.0.0', PROXY_PORT), ProxyHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 服务已停止")
    except Exception as e:
        print(f"\n❌ 服务器错误: {e}")
    finally:
        try:
            from pyngrok import ngrok
            ngrok.kill()
        except:
            pass


if __name__ == '__main__':
    main()
