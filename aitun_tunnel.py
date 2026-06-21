#!/usr/bin/env python3
"""
aitun_tunnel.py — AiTun 隧道管理器

为 ColabMCP 提供 aitun.cc 免注册隧道的封装，包含：

- 自动安装 aitun-client 二进制（来自 aitun.cc 官方下载）
- 免注册模式（默认）：无需 token，自动分配公网 URL
- 注册模式（可选）：使用 -k TOKEN --subdomain NAME 获取固定子域名
- 子进程守护线程：进程退出后自动重启
- URL 解析：从 aitun-client stdout 提取 `https://aitun.cc/XXXXXXXX`
- 健康探测：启动后通过本地 /health 端点验证隧道可用
- Colab 兼容：自动加 --no-p2p，避免 P2P 检测阻塞
- 优雅退出：随主进程退出自动 kill 子进程

用法（独立运行）：

    python aitun_tunnel.py --port 5000
    python aitun_tunnel.py --port 5000 --token YOUR_TOKEN --subdomain myname
    python aitun_tunnel.py --port 5000 --no-p2p

作为库使用：

    from aitun_tunnel import AiTunTunnel
    t = AiTunTunnel(local_port=5000)
    t.start()  # 阻塞，自动重连；Ctrl+C 退出
"""

from __future__ import annotations

import os
import re
import sys
import time
import shutil
import signal
import subprocess
import threading
import platform
import urllib.request
import urllib.error
from typing import Optional, Callable, List


# ============== 常量 ==============

AITUN_BIN_NAME = "aitun"
AITUN_INSTALL_PATHS = [
    "/usr/local/bin/aitun",
    os.path.expanduser("~/.local/bin/aitun"),
    os.path.expanduser("/usr/bin/aitun"),
    "/usr/bin/aitun",
    "/usr/local/bin/aitun",
]

AITUN_DOWNLOAD_BASE = "https://aitun.cc/downloads"
AITUN_INSTALL_SCRIPT = "https://aitun.cc/install.sh"

# 默认服务器（可被 -s/--server 覆盖）
DEFAULT_SERVER = "aitun.cc:6639"

# 重试与超时
MAX_STARTUP_WAIT = 60        # 启动后最多等待 60s 拿到 URL
RECONNECT_DELAY = 3          # 进程退出后等待 3s 再重启
RECONNECT_BACKOFF_MAX = 30   # 退避上限
HEALTH_PROBE_TIMEOUT = 5     # 本地 /health 探测超时
HEALTH_PROBE_INTERVAL = 30   # 每 30s 主动探测一次本地服务


# ============== 工具函数 ==============

def detect_platform() -> str:
    """检测当前平台的下载标识，如 'linux-amd64'。"""
    os_name = platform.system().lower()
    arch = platform.machine().lower()
    if os_name == "linux":
        platform_os = "linux"
    elif os_name == "darwin":
        platform_os = "darwin"
    elif os_name in ("mingw", "msys", "cygwin", "windows"):
        platform_os = "windows"
    else:
        platform_os = "linux"

    if arch in ("x86_64", "amd64"):
        platform_arch = "amd64"
    elif arch in ("aarch64", "arm64"):
        platform_arch = "arm64"
    else:
        platform_arch = "amd64"

    return f"{platform_os}-{platform_arch}"


def find_aitun_binary() -> Optional[str]:
    """查找已安装的 aitun 二进制路径。"""
    # 1. PATH 中查找
    found = shutil.which(AITUN_BIN_NAME)
    if found:
        return found
    # 2. 已知安装路径
    for p in AITUN_INSTALL_PATHS:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def install_aitun(force: bool = False, verbose: bool = True) -> str:
    """
    安装 aitun-client 二进制。

    优先使用官方 install.sh；失败则直接下载二进制。

    Returns:
        aitun 二进制的绝对路径。

    Raises:
        RuntimeError: 安装失败。
    """
    if not force:
        existing = find_aitun_binary()
        if existing:
            if verbose:
                print(f"[aitun] 已安装: {existing}")
            return existing

    # 方式 1：官方 install.sh（带 SHA256 校验，最稳）
    if verbose:
        print("[aitun] 通过官方 install.sh 安装...")
    try:
        result = subprocess.run(
            ["bash", "-c", f"curl -fsSL {AITUN_INSTALL_SCRIPT} | bash"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            installed = find_aitun_binary()
            if installed:
                if verbose:
                    print(f"[aitun] 安装成功: {installed}")
                return installed
            # install.sh 装到了 ~/.local/bin 但 PATH 没刷新
            for p in AITUN_INSTALL_PATHS:
                if os.path.isfile(p) and os.access(p, os.X_OK):
                    if verbose:
                        print(f"[aitun] 安装成功: {p}")
                    return p
        else:
            if verbose:
                print(f"[aitun] install.sh 失败 (rc={result.returncode}): {result.stderr[:300]}")
    except Exception as e:
        if verbose:
            print(f"[aitun] install.sh 异常: {e}")

    # 方式 2：直接下载二进制（fallback）
    if verbose:
        print("[aitun] 尝试直接下载二进制...")
    plat = detect_platform()
    binary_name = f"aitun-client-{plat}"
    url = f"{AITUN_DOWNLOAD_BASE}/{binary_name}"
    target_dir = os.path.expanduser("~/.local/bin")
    os.makedirs(target_dir, exist_ok=True)
    target = os.path.join(target_dir, AITUN_BIN_NAME)
    if plat == "windows-amd64":
        target += ".exe"

    try:
        if verbose:
            print(f"[aitun] 下载 {url} -> {target}")
        urllib.request.urlretrieve(url, target)
        os.chmod(target, 0o755)
        if verbose:
            print(f"[aitun] 下载完成: {target}")
        return target
    except Exception as e:
        raise RuntimeError(
            f"无法安装 aitun-client。请手动执行: "
            f"curl -fsSL {AITUN_INSTALL_SCRIPT} | bash\n错误: {e}"
        )


def parse_public_url(line: str) -> Optional[str]:
    """从 aitun-client 输出行中解析公网 URL。"""
    # [OK] Proxy URL: https://aitun.cc/UKMA9N10
    m = re.search(r"https?://(?:[\w.-]+\.)?aitun\.cc/[A-Za-z0-9]+", line)
    if m:
        return m.group(0).rstrip(".,;\"'")
    return None


def parse_tunnel_code(line: str) -> Optional[str]:
    """从 aitun-client 输出行中解析隧道编码。"""
    # [OK] Tunnel code: UKMA9N10
    m = re.search(r"\[OK\]\s*Tunnel code:\s*([A-Za-z0-9]+)", line)
    if m:
        return m.group(1)
    return None


def probe_local_health(port: int, timeout: float = HEALTH_PROBE_TIMEOUT) -> bool:
    """探测本地端口上的 /health 端点是否响应。"""
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/health", timeout=timeout
        ) as resp:
            return resp.status == 200
    except Exception:
        return False


# ============== 隧道管理器 ==============

class AiTunTunnel:
    """
    AiTun 隧道守护器。

    在子进程中运行 aitun-client，监控其 stdout 解析公网 URL，
    进程意外退出后自动重启，主进程退出时清理子进程。
    """

    def __init__(
        self,
        local_port: int,
        local_host: str = "localhost",
        token: Optional[str] = None,
        subdomain: Optional[str] = None,
        no_p2p: bool = True,
        server: str = DEFAULT_SERVER,
        binary: Optional[str] = None,
        auto_install: bool = True,
        on_url: Optional[Callable[[str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_reconnect: Optional[Callable[[int, str], None]] = None,
        verbose: bool = True,
    ):
        """
        Args:
            local_port: 本地服务端口（必须先于隧道启动）。
            local_host: 本地服务主机，默认 localhost。
            token: 可选，注册用户的认证 token；为空则使用免注册模式。
            subdomain: 可选，注册模式下的子域名前缀。
            no_p2p: 关闭 P2P 直连，强制服务器中继（Colab 推荐开启）。
            server: aitun 服务器地址，默认 aitun.cc:6639。
            binary: aitun 二进制路径；为空则自动查找/安装。
            auto_install: 二进制不存在时是否自动安装。
            on_url: 拿到公网 URL 时的回调。
            on_log: 收到 aitun-client 输出时的回调。
            on_reconnect: 触发重连时的回调 (attempt, reason)。
            verbose: 是否在 stdout 打印日志。
        """
        self.local_port = local_port
        self.local_host = local_host
        self.token = token or ""
        self.subdomain = subdomain
        self.no_p2p = no_p2p
        self.server = server
        self.binary = binary
        self.auto_install = auto_install
        self.on_url = on_url
        self.on_log = on_log
        self.on_reconnect = on_reconnect
        self.verbose = verbose

        # 运行时状态
        self._proc: Optional[subprocess.Popen] = None
        self._public_url: Optional[str] = None
        self._tunnel_code: Optional[str] = None
        self._stop_event = threading.Event()
        self._reader_thread: Optional[threading.Thread] = None
        self._watchdog_thread: Optional[threading.Thread] = None
        self._health_thread: Optional[threading.Thread] = None
        self._reconnect_count = 0
        self._lock = threading.Lock()

    # ---------- 日志 ----------

    def _log(self, msg: str):
        line = f"[aitun] {msg}"
        if self.verbose:
            print(line, flush=True)
        if self.on_log:
            try:
                self.on_log(line)
            except Exception:
                pass

    # ---------- 二进制 ----------

    def _ensure_binary(self) -> str:
        if self.binary and os.path.isfile(self.binary):
            return self.binary
        existing = find_aitun_binary()
        if existing:
            self.binary = existing
            return existing
        if not self.auto_install:
            raise RuntimeError(
                "未找到 aitun-client，且 auto_install=False。"
                f"请手动安装: curl -fsSL {AITUN_INSTALL_SCRIPT} | bash"
            )
        self.binary = install_aitun(verbose=self.verbose)
        return self.binary

    # ---------- 命令构建 ----------

    def _build_cmd(self) -> List[str]:
        cmd = [
            self.binary,
            "-p", str(self.local_port),
            "-host", self.local_host,
            "-s", self.server,
        ]
        if self.token:
            cmd.extend(["-k", self.token])
        if self.subdomain and self.token:
            cmd.extend(["--subdomain", self.subdomain])
        if self.no_p2p:
            cmd.append("--no-p2p")
        return cmd

    # ---------- 子进程读取 ----------

    def _reader_loop(self):
        """从子进程 stdout 读取并解析。"""
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        for line in iter(proc.stdout.readline, ""):
            if not line:
                break
            line_stripped = line.rstrip()
            if line_stripped:
                self._log(f"[client] {line_stripped}")
            # 解析 URL
            url = parse_public_url(line)
            if url:
                with self._lock:
                    if self._public_url != url:
                        self._public_url = url
                        self._log(f"📡 公网 URL: {url}")
                        if self.on_url:
                            try:
                                self.on_url(url)
                            except Exception as e:
                                self._log(f"on_url 回调异常: {e}")
            # 解析 tunnel code
            code = parse_tunnel_code(line)
            if code:
                with self._lock:
                    self._public_url = self._public_url or f"https://aitun.cc/{code}"
                    self._tunnel_code = code

    # ---------- 健康探测线程 ----------

    def _health_loop(self):
        """周期性探测本地服务，若不健康则 kill aitun 触发重启。"""
        while not self._stop_event.is_set():
            try:
                time.sleep(HEALTH_PROBE_INTERVAL)
                if self._stop_event.is_set():
                    break
                ok = probe_local_health(self.local_port)
                if not ok:
                    self._log("⚠️ 本地服务无响应，触发隧道重连...")
                    self._kill_proc()
            except Exception as e:
                self._log(f"健康探测异常: {e}")

    # ---------- 看门狗 ----------

    def _watchdog_loop(self):
        """监控子进程，退出后自动重启。"""
        delay = RECONNECT_DELAY
        while not self._stop_event.is_set():
            try:
                proc = self._proc
                if proc is None:
                    break

                # 等待进程退出
                while proc.poll() is None and not self._stop_event.is_set():
                    time.sleep(1.0)

                if self._stop_event.is_set():
                    break

                # 进程已退出
                rc = proc.returncode
                self._reconnect_count += 1
                reason = f"子进程退出 (rc={rc})"
                self._log(f"⚠️ {reason}，{delay}s 后重启 (第 {self._reconnect_count} 次)...")
                if self.on_reconnect:
                    try:
                        self.on_reconnect(self._reconnect_count, reason)
                    except Exception:
                        pass

                if self._stop_event.wait(delay):
                    break

                # 退避策略：每次 +2s，上限 30s
                delay = min(delay + 2, RECONNECT_BACKOFF_MAX)

                # 重置 URL（重启后 URL 会变化）
                with self._lock:
                    self._public_url = None
                    self._tunnel_code = None

                # 重启子进程
                self._spawn_proc()

                # 重置退避（成功启动后）
                delay = RECONNECT_DELAY

            except Exception as e:
                self._log(f"看门狗异常: {e}")
                time.sleep(RECONNECT_DELAY)

    def _spawn_proc(self):
        """启动 aitun-client 子进程。"""
        cmd = self._build_cmd()
        self._log(f"启动: {' '.join(cmd)}")
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                # 给子进程一个独立进程组，便于清理
                start_new_session=True,
            )
        except FileNotFoundError:
            self._log("❌ 找不到 aitun 二进制，尝试重新安装...")
            self.binary = None
            self._ensure_binary()
            self._proc = subprocess.Popen(
                self._build_cmd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )

        # 启动 reader 线程
        self._reader_thread = threading.Thread(
            target=self._reader_loop, name="aitun-reader", daemon=True
        )
        self._reader_thread.start()

    def _kill_proc(self):
        """终止当前子进程。"""
        proc = self._proc
        if proc is None:
            return
        try:
            if proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except (ProcessLookupError, PermissionError, OSError):
                    proc.terminate()
                # 等待 3s 让它优雅退出
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except (ProcessLookupError, PermissionError, OSError):
                        proc.kill()
                    proc.wait(timeout=2)
        except Exception as e:
            self._log(f"终止子进程异常: {e}")

    # ---------- 公共接口 ----------

    def start(self, block: bool = True):
        """
        启动隧道。

        Args:
            block: 是否阻塞调用线程。False 时仅启动守护线程后立即返回。
        """
        self._ensure_binary()
        self._spawn_proc()

        # 看门狗线程
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop, name="aitun-watchdog", daemon=True
        )
        self._watchdog_thread.start()

        # 健康探测线程
        self._health_thread = threading.Thread(
            target=self._health_loop, name="aitun-health", daemon=True
        )
        self._health_thread.start()

        # 注册信号处理（主线程）
        try:
            signal.signal(signal.SIGTERM, self._signal_handler)
        except (ValueError, OSError):
            pass  # 非主线程

        if block:
            try:
                while not self._stop_event.is_set():
                    time.sleep(1.0)
            except KeyboardInterrupt:
                self._log("收到中断信号，停止...")
            finally:
                self.stop()

    def stop(self):
        """停止隧道并清理资源。"""
        self._stop_event.set()
        self._kill_proc()
        self._log("已停止")

    def _signal_handler(self, signum, frame):
        self._log(f"收到信号 {signum}，停止隧道...")
        self.stop()

    @property
    def public_url(self) -> Optional[str]:
        with self._lock:
            return self._public_url

    @property
    def tunnel_code(self) -> Optional[str]:
        with self._lock:
            return self._tunnel_code

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def wait_for_url(self, timeout: float = MAX_STARTUP_WAIT) -> Optional[str]:
        """阻塞等待公网 URL 出现，超时返回当前值。"""
        start = time.time()
        while time.time() - start < timeout:
            url = self.public_url
            if url:
                return url
            if self._stop_event.is_set():
                break
            time.sleep(0.3)
        return self.public_url


# ============== CLI ==============

def _cli_main():
    import argparse

    parser = argparse.ArgumentParser(
        description="AiTun 隧道守护器 — aitun.cc 免注册隧道",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 免注册模式（自动分配 URL）
  python aitun_tunnel.py -p 5000

  # 注册模式（固定子域名）
  python aitun_tunnel.py -p 5000 -k TOKEN --subdomain myname

  # 禁用 --no-p2p（启用 P2P 直连）
  python aitun_tunnel.py -p 5000 --p2p
""",
    )
    parser.add_argument("-p", "--port", type=int, required=True, help="本地服务端口")
    parser.add_argument("--host", default="localhost", help="本地服务主机")
    parser.add_argument("-k", "--token", default="", help="aitun.cc 认证 token（留空则免注册）")
    parser.add_argument("--subdomain", default=None, help="子域名前缀（需要 token）")
    parser.add_argument("--server", default=DEFAULT_SERVER, help="aitun 服务器地址")
    parser.add_argument("--p2p", action="store_true", help="启用 P2P 直连（默认关闭）")
    parser.add_argument("--install-only", action="store_true", help="仅安装二进制后退出")
    parser.add_argument("-q", "--quiet", action="store_true", help="安静模式")

    args = parser.parse_args()

    if args.install_only:
        path = install_aitun(verbose=not args.quiet)
        print(f"已安装: {path}")
        return

    tunnel = AiTunTunnel(
        local_port=args.port,
        local_host=args.host,
        token=args.token,
        subdomain=args.subdomain,
        no_p2p=not args.p2p,
        server=args.server,
        verbose=not args.quiet,
        on_url=lambda url: print(f"\n{'='*60}\n🎉 公网 URL: {url}\n{'='*60}\n"),
    )

    print("=" * 60)
    print("🚇 AiTun 隧道守护器启动")
    print("=" * 60)
    print(f"  本地:   {args.host}:{args.port}")
    print(f"  服务器: {args.server}")
    print(f"  模式:   {'注册（子域名）' if args.token else '免注册（自动分配）'}")
    print(f"  P2P:    {'启用' if args.p2p else '禁用（强制中继，Colab 推荐）'}")
    print("=" * 60)
    print()

    tunnel.start(block=True)


if __name__ == "__main__":
    _cli_main()
