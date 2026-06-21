#!/usr/bin/env python3
"""
ColabMCP Server v2.0.0 - 稳定版

变更说明 (相对 v1.x):
- 单一命名空间 exec(): 变量跨请求持久化，异常时也保存
- 新增 /status: 实时查看执行状态、当前目录、最近命令
- 新增 /history: 查看命令历史
- 新增 /interrupt: 中断当前执行（不停止服务器）
- 新增 /execute_stream: SSE 实时流式输出（适合长时间任务）
- 心跳优化: 不再请求 /health，避免与执行锁冲突
- 超时延长: 默认 600s，最大 1800s
- 异常时保存已定义变量，部分执行结果不丢失

部署场景:
- ModelScope 创空间: 直接运行，端口 7860，无需隧道
- Google Colab: 配合 aitun_tunnel.py 暴露公网（参见 colab_mcp_server.ipynb）
- 本地开发: python app.py [--port 7860]
"""

import os
import sys
import json
import time
import traceback
import subprocess
import gc
import threading
import signal
import ctypes
import queue
import re
import logging
from datetime import datetime
from io import StringIO
from flask import Flask, request, jsonify, Response

try:
    import psutil
except ImportError:
    subprocess.run(['pip', 'install', 'psutil', '-q'], check=True)
    import psutil


# ============== Flask 日志降噪 ==============
# 问题：werkzeug 的 WSGI 请求处理器会用 logging 写访问日志。
# /execute_stream 会把 sys.stderr 重定向到 StringIO 捕获用户代码输出，
# 导致：1) werkzeug 的访问日志被混入 SSE；2) handler 写入失败时 logging 把
# "--- Logging error ---" traceback 写到 sys.stderr（已被重定向），进一步污染 SSE。
# 解决：用 NullHandler 完全吞掉 werkzeug 的日志，且 raiseExceptions=False 双保险。
logging.raiseExceptions = False

class _NullHandler(logging.Handler):
    """完全吞掉所有日志，不写入任何流。"""
    def emit(self, record):
        pass
    def handle(self, record):
        return True

# werkzeug logger — 屏蔽访问日志（INFO 级），保留 CRITICAL 不输出（避免污染 SSE）
_werkzug_logger = logging.getLogger('werkzeug')
_werkzug_logger.handlers = [_NullHandler()]
_werkzug_logger.setLevel(logging.CRITICAL + 1)  # 屏蔽所有级别
_werkzug_logger.propagate = False

# Flask app logger
_flask_logger = logging.getLogger('flask.app')
_flask_logger.handlers = [_NullHandler()]
_flask_logger.setLevel(logging.WARNING)
_flask_logger.propagate = False

# Root logger — 也用 NullHandler，避免其他 logger 输出污染 SSE
logging.getLogger().handlers = [_NullHandler()]
logging.getLogger().setLevel(logging.WARNING)


# ============== 全局状态 ==============
runtime_variables = {}
start_time = time.time()
execution_lock = threading.Lock()
keep_running = True

# 执行状态跟踪
WORK_DIR_DEFAULT = os.environ.get("COLABMCP_WORKDIR", "/content" if os.path.isdir("/content") else os.getcwd())
execution_state = {
    "current_directory": WORK_DIR_DEFAULT,
    "is_executing": False,
    "last_command": "",
    "last_execution_time": 0,
    "last_error": None,
    "command_history": [],
    "started_at": start_time,
}

# 当前执行的线程引用
current_execution_thread = None
interrupt_requested = False

# 流式输出队列
stream_output_queue = None
stream_active = False

# 创建 Flask 应用
app = Flask(__name__)


# ============== 辅助函数：变量保存 ==============
# 内置 key 集合，用于过滤 exec() 命名空间里的内置项
_BUILTIN_KEYS = set(dir(__builtins__)) if isinstance(__builtins__, dict) else set(dir(__builtins__))
_BUILTIN_KEYS.update(['__builtins__'])


def _save_variables(namespace, keys_before):
    """将命名空间中的变量保存到 runtime_variables（单一命名空间方案）。

    异常时也调用此函数，避免部分执行结果丢失。
    """
    saved_keys = []
    for key, value in namespace.items():
        if key.startswith('_') or key in _BUILTIN_KEYS:
            continue
        if key in keys_before and namespace[key] is keys_before[key]:
            continue  # 未变更，跳过
        try:
            runtime_variables[key] = value
            saved_keys.append(key)
        except Exception:
            pass
    return saved_keys


# ============== 心跳保活线程 ==============
def heartbeat_thread():
    """心跳线程，防止 Colab 休眠。

    v2.0 优化：不再请求 /health，避免与执行锁冲突。
    仅打印心跳日志 + 维持 Python 活跃。
    """
    while keep_running:
        try:
            current_time = time.strftime("%H:%M:%S")
            is_exec = execution_state['is_executing']
            exec_flag = " [执行中]" if is_exec else ""
            print(f"[心跳] {current_time} - 运行中 | 目录: {execution_state['current_directory']}{exec_flag}", flush=True)
            time.sleep(60)
        except Exception as e:
            print(f"[心跳错误] {e}", flush=True)
            time.sleep(30)


# ============== 辅助函数 ==============
def _check_gpu():
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False


def _add_to_history(command, output_preview="", success=True):
    """添加命令到历史记录。"""
    entry = {
        "command": command[:500],
        "output_preview": output_preview[:200],
        "timestamp": time.time(),
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "directory": execution_state["current_directory"],
        "success": success
    }
    execution_state["command_history"].append(entry)
    if len(execution_state["command_history"]) > 100:
        execution_state["command_history"] = execution_state["command_history"][-100:]


def _update_directory_from_code(code):
    """从代码中提取目录变化（os.chdir / %cd）。"""
    # os.chdir('...')
    match = re.search(r"os\.chdir\(['\"]([^'\"]+)['\"]\)", code)
    if match:
        new_dir = match.group(1)
        execution_state["current_directory"] = new_dir
        return new_dir
    # %cd ...
    match = re.search(r"(?:^|\n)%cd\s+(.+?)(?:\n|$)", code)
    if match:
        new_dir = match.group(1).strip().strip('"\'')
        execution_state["current_directory"] = new_dir
        return new_dir
    return None


def _interrupt_thread(thread):
    """尝试中断线程中的执行（通过注入异常）。"""
    global interrupt_requested
    interrupt_requested = True
    if thread and thread.is_alive():
        try:
            thread_id = thread.ident
            if thread_id:
                exc = KeyboardInterrupt()
                ctypes.pythonapi.PyThreadState_SetAsyncExc(
                    ctypes.c_long(thread_id),
                    ctypes.py_object(exc)
                )
        except Exception as e:
            print(f"[中断] 尝试中断失败: {e}", flush=True)
    return True


# ============== API Endpoints ==============
@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "name": "ColabMCP Server",
        "version": "2.0.0",
        "status": "running",
        "uptime_minutes": round((time.time() - start_time) / 60, 2),
        "current_directory": execution_state["current_directory"],
        "is_executing": execution_state["is_executing"],
        "variables_count": len(runtime_variables),
        "endpoints": [
            "/health", "/probe", "/execute", "/execute_stream",
            "/interrupt", "/status", "/history",
            "/variables", "/files", "/cleanup"
        ]
    })


@app.route('/health', methods=['GET'])
def health_check():
    mem = psutil.virtual_memory()
    return jsonify({
        "status": "ok",
        "uptime_minutes": round((time.time() - start_time) / 60, 2),
        "memory_available_gb": round(mem.available / (1024**3), 2),
        "memory_total_gb": round(mem.total / (1024**3), 2),
        "memory_used_pct": round(mem.percent, 2),
        "gpu_available": _check_gpu(),
        "current_directory": execution_state["current_directory"],
        "is_executing": execution_state["is_executing"],
        "variables_count": len(runtime_variables)
    })


@app.route('/status', methods=['GET'])
def get_status():
    """获取详细执行状态。"""
    return jsonify({
        "status": "ok",
        "current_directory": execution_state["current_directory"],
        "is_executing": execution_state["is_executing"],
        "last_command": execution_state["last_command"],
        "last_execution_time": execution_state["last_execution_time"],
        "last_error": execution_state["last_error"],
        "recent_history": [h["command"] for h in execution_state["command_history"][-5:]],
        "variables_count": len(runtime_variables),
        "uptime_minutes": round((time.time() - start_time) / 60, 2)
    })


@app.route('/history', methods=['GET'])
def get_history():
    """获取命令历史。"""
    limit = request.args.get('limit', 20, type=int)
    limit = min(limit, 100)
    history = execution_state["command_history"][-limit:]
    return jsonify({"history": history, "total": len(execution_state["command_history"])})


@app.route('/interrupt', methods=['POST'])
def interrupt_execution():
    """中断当前执行（不停止服务器）。"""
    global interrupt_requested, current_execution_thread

    if not execution_state["is_executing"]:
        return jsonify({"success": True, "message": "当前没有正在执行的任务"})

    interrupt_requested = True

    if current_execution_thread and current_execution_thread.is_alive():
        success = _interrupt_thread(current_execution_thread)
        if success:
            execution_state["is_executing"] = False
            execution_state["last_error"] = "用户中断"
            return jsonify({"success": True, "message": "已发送中断信号"})
        else:
            return jsonify({"success": False, "message": "中断失败，请稍后重试"})

    return jsonify({"success": True, "message": "中断请求已处理"})


@app.route('/probe', methods=['GET'])
def probe_environment():
    gpu_info = ""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total,memory.free', '--format=csv'],
            capture_output=True, text=True, timeout=10
        )
        gpu_info = result.stdout
    except Exception:
        gpu_info = "No GPU available"

    installed_packages = []
    try:
        result = subprocess.run(
            ['pip', 'list', '--format=freeze'],
            capture_output=True, text=True, timeout=30
        )
        for line in result.stdout.split('\n'):
            if '==' in line:
                installed_packages.append(line.strip())
    except Exception:
        pass

    mem = psutil.virtual_memory()

    return jsonify({
        "gpu_info": gpu_info,
        "memory_total_gb": round(mem.total / (1024**3), 2),
        "memory_available_gb": round(mem.available / (1024**3), 2),
        "python_version": sys.version,
        "current_directory": execution_state["current_directory"],
        "installed_packages": installed_packages[:100],
        "total_packages": len(installed_packages)
    })


@app.route('/execute', methods=['POST'])
def execute_code():
    """执行 Python 代码，带错误隔离和状态跟踪（单一命名空间，变量跨请求持久化）。"""
    global current_execution_thread, interrupt_requested

    if not execution_lock.acquire(blocking=False):
        return jsonify({"success": False, "error": "另一个代码正在执行中，请稍后重试"})

    interrupt_requested = False
    current_execution_thread = threading.current_thread()

    try:
        data = request.get_json()
        code = data.get('code', '')
        timeout = min(data.get('timeout', 600), 1800)

        if not code:
            return jsonify({"success": False, "error": "No code provided"})

        execution_state["is_executing"] = True
        execution_state["last_command"] = code[:200] + "..." if len(code) > 200 else code

        # ★ 核心修复：使用单一命名空间，避免 exec() 双命名空间变量丢失问题
        exec_namespace = {'__builtins__': __builtins__, **runtime_variables}
        keys_before = dict(exec_namespace)  # 快照执行前的 key→value 映射

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = captured_stdout = StringIO()
        sys.stderr = captured_stderr = StringIO()

        start_exec_time = time.time()
        saved_keys = []

        try:
            if interrupt_requested:
                raise KeyboardInterrupt("执行被用户中断")

            exec(code, exec_namespace)  # 单一命名空间：变量直接在 namespace 中

            if interrupt_requested:
                raise KeyboardInterrupt("执行被用户中断")

            # 保存新增/变更的变量
            saved_keys = _save_variables(exec_namespace, keys_before)

            _update_directory_from_code(code)
            stdout_val = captured_stdout.getvalue()
            _add_to_history(code, stdout_val, success=True)

            execution_state["last_execution_time"] = time.time() - start_exec_time
            execution_state["last_error"] = None

            return jsonify({
                "success": True,
                "stdout": stdout_val,
                "stderr": captured_stderr.getvalue(),
                "execution_time_sec": round(time.time() - start_exec_time, 3),
                "variables": saved_keys,
                "current_directory": execution_state["current_directory"]
            })

        except KeyboardInterrupt:
            # 异常时也保存已定义的变量
            saved_keys = _save_variables(exec_namespace, keys_before)
            stdout_val = captured_stdout.getvalue()
            _add_to_history(code, stdout_val, success=False)
            execution_state["last_error"] = "用户中断"
            return jsonify({
                "success": False,
                "error": "执行被用户中断",
                "error_type": "KeyboardInterrupt",
                "stdout": stdout_val,
                "stderr": captured_stderr.getvalue(),
                "execution_time_sec": round(time.time() - start_exec_time, 3),
                "variables_saved": saved_keys
            })

        except Exception as e:
            # 异常时也保存已定义的变量（部分执行结果不丢失）
            saved_keys = _save_variables(exec_namespace, keys_before)
            stdout_val = captured_stdout.getvalue()
            _add_to_history(code, stdout_val, success=False)
            execution_state["last_error"] = str(e)
            return jsonify({
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc(),
                "stdout": stdout_val,
                "stderr": captured_stderr.getvalue(),
                "execution_time_sec": round(time.time() - start_exec_time, 3),
                "variables_saved": saved_keys
            })

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            execution_state["is_executing"] = False

    except Exception as e:
        execution_state["is_executing"] = False
        return jsonify({
            "success": False,
            "error": f"服务器内部错误: {str(e)}",
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        })

    finally:
        execution_lock.release()
        current_execution_thread = None


@app.route('/execute_stream', methods=['POST'])
def execute_code_stream():
    """
    流式执行代码 - 使用 SSE 实时推送输出。
    ★ 使用单一命名空间，变量跨请求持久化
    """
    global stream_output_queue, stream_active, interrupt_requested

    def generate_sse(output_queue):
        """SSE 生成器"""
        try:
            while True:
                try:
                    msg = output_queue.get(timeout=0.5)
                    if msg is None:
                        break
                    yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    yield f": heartbeat\n\n"
                    continue
        except GeneratorExit:
            pass

    stream_output_queue = queue.Queue()
    stream_active = True
    interrupt_requested = False

    data = request.get_json()
    code = data.get('code', '')
    timeout = min(data.get('timeout', 600), 1800)

    if not code:
        stream_output_queue.put({"type": "error", "content": "No code provided"})
        stream_output_queue.put(None)
        return Response(generate_sse(stream_output_queue), mimetype='text/event-stream')

    execution_state["is_executing"] = True
    execution_state["last_command"] = code[:200] + "..." if len(code) > 200 else code

    stripped_code = code.strip()

    # 检测 shell 命令模式（兼容 colabcli_tc 的格式）
    shell_match = re.match(r'^import subprocess; result = subprocess\.run\([\'"](.+?)[\'"], shell=True', stripped_code)
    if shell_match:
        shell_cmd = shell_match.group(1)

        def run_shell_command():
            global stream_active
            start_time_exec = time.time()
            stream_output_queue.put({"type": "status", "content": f"执行: {shell_cmd}"})

            try:
                process = subprocess.Popen(
                    shell_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    cwd=execution_state["current_directory"]
                )

                import select
                while True:
                    if interrupt_requested:
                        process.terminate()
                        stream_output_queue.put({"type": "error", "content": "执行被用户中断"})
                        break

                    retcode = process.poll()
                    read_ready, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)

                    for stream in read_ready:
                        if stream == process.stdout:
                            line = process.stdout.readline()
                            if line:
                                stream_output_queue.put({"type": "stdout", "content": line})
                        elif stream == process.stderr:
                            line = process.stderr.readline()
                            if line:
                                stream_output_queue.put({"type": "stderr", "content": line})

                    if retcode is not None:
                        remaining_stdout, remaining_stderr = process.communicate()
                        if remaining_stdout:
                            stream_output_queue.put({"type": "stdout", "content": remaining_stdout})
                        if remaining_stderr:
                            stream_output_queue.put({"type": "stderr", "content": remaining_stderr})
                        break

                elapsed = time.time() - start_time_exec
                stream_output_queue.put({
                    "type": "complete",
                    "content": f"完成 (退出码: {process.returncode}, 耗时: {elapsed:.2f}s)"
                })
                _add_to_history(code, f"shell: {shell_cmd}", success=True)
                execution_state["last_execution_time"] = elapsed

            except Exception as e:
                stream_output_queue.put({"type": "error", "content": str(e)})
                _add_to_history(code, str(e), success=False)
            finally:
                stream_output_queue.put(None)
                stream_active = False
                execution_state["is_executing"] = False

        thread = threading.Thread(target=run_shell_command, daemon=True)
        thread.start()

    else:
        class StreamingOutput:
            """流式输出捕获器"""
            def __init__(self, q, stream_type):
                self.queue = q
                self.stream_type = stream_type
                self.buffer = []

            def write(self, text):
                if text:
                    self.buffer.append(text)
                    self.queue.put({"type": self.stream_type, "content": text})

            def flush(self):
                pass

            def getvalue(self):
                return ''.join(self.buffer)

        def run_python_code():
            global stream_active
            start_time_exec = time.time()
            stream_output_queue.put({"type": "status", "content": "执行 Python 代码..."})

            old_stdout = sys.stdout
            old_stderr = sys.stderr
            stdout_capture = StreamingOutput(stream_output_queue, 'stdout')
            stderr_capture = StreamingOutput(stream_output_queue, 'stderr')
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture

            exec_namespace = {'__builtins__': __builtins__, **runtime_variables}
            keys_before = dict(exec_namespace)
            saved_keys = []

            try:
                if interrupt_requested:
                    raise KeyboardInterrupt("执行被用户中断")

                exec(code, exec_namespace)

                if interrupt_requested:
                    raise KeyboardInterrupt("执行被用户中断")

                saved_keys = _save_variables(exec_namespace, keys_before)
                _update_directory_from_code(code)
                elapsed = time.time() - start_time_exec
                stream_output_queue.put({
                    "type": "complete",
                    "content": f"完成 (耗时: {elapsed:.2f}s)",
                    "variables": saved_keys
                })
                _add_to_history(code, ''.join(stdout_capture.buffer)[:200], success=True)
                execution_state["last_execution_time"] = elapsed

            except KeyboardInterrupt:
                saved_keys = _save_variables(exec_namespace, keys_before)
                stream_output_queue.put({"type": "error", "content": "执行被用户中断", "variables_saved": saved_keys})
                _add_to_history(code, "中断", success=False)
            except Exception as e:
                saved_keys = _save_variables(exec_namespace, keys_before)
                stream_output_queue.put({
                    "type": "error",
                    "content": f"错误: {type(e).__name__}: {str(e)}",
                    "variables_saved": saved_keys
                })
                _add_to_history(code, str(e), success=False)
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                stream_output_queue.put(None)
                stream_active = False
                execution_state["is_executing"] = False

        thread = threading.Thread(target=run_python_code, daemon=True)
        thread.start()

    return Response(generate_sse(stream_output_queue), mimetype='text/event-stream')


@app.route('/variables', methods=['GET'])
def list_variables():
    vars_info = {}
    for key, value in runtime_variables.items():
        try:
            var_info = {"type": str(type(value).__name__)}
            if hasattr(value, 'shape'):
                var_info["shape"] = list(value.shape) if hasattr(value.shape, '__iter__') else str(value.shape)
            if hasattr(value, '__len__'):
                try:
                    var_info["length"] = len(value)
                except Exception:
                    pass
            vars_info[key] = var_info
        except Exception:
            vars_info[key] = {"type": str(type(value).__name__)}

    return jsonify({
        "variables": vars_info,
        "count": len(vars_info),
        "current_directory": execution_state["current_directory"]
    })


@app.route('/files', methods=['GET'])
def list_files():
    content_dir = execution_state.get("current_directory", WORK_DIR_DEFAULT)
    dir_param = request.args.get('dir', None)
    if dir_param:
        content_dir = dir_param

    files = []
    try:
        for f in os.listdir(content_dir):
            path = os.path.join(content_dir, f)
            try:
                size = os.path.getsize(path)
                files.append({
                    "name": f,
                    "path": path,
                    "size_bytes": size,
                    "size_readable": f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/1024/1024:.1f} MB",
                    "is_dir": os.path.isdir(path)
                })
            except Exception:
                pass
    except Exception as e:
        return jsonify({"error": str(e), "files": [], "directory": content_dir})

    return jsonify({"files": files, "count": len(files), "directory": content_dir})


@app.route('/cleanup', methods=['POST'])
def cleanup():
    global runtime_variables
    runtime_variables = {}
    gc.collect()

    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    mem = psutil.virtual_memory()
    return jsonify({
        "success": True,
        "message": "Memory cleaned",
        "memory_available_gb": round(mem.available / (1024**3), 2)
    })


# ============== 信号处理 ==============
def signal_handler(sig, frame):
    global keep_running
    print("\n[信号] 收到停止信号，正在关闭...")
    keep_running = False
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    port = int(os.environ.get('PORT', 7860))

    print("\n" + "="*60)
    print("🚀 ColabMCP 服务器启动中...")
    print("="*60)
    print(f"版本: 2.0.0 (稳定版)")
    print(f"端口: {port}")
    print(f"工作目录: {WORK_DIR_DEFAULT}")
    print("功能: 心跳保活 + 错误隔离 + 中断支持 + 状态跟踪 + 流式输出")
    print("核心: 单一命名空间 exec() - 变量跨请求持久化")
    print("优化: 异常时也保存变量 + 长任务稳定支持 + 600s超时")
    print("="*60 + "\n")

    heartbeat = threading.Thread(target=heartbeat_thread, daemon=True)
    heartbeat.start()

    try:
        # threaded=True 支持多请求并发；use_reloader=False 避免子进程干扰隧道
        app.run(port=port, host='0.0.0.0', threaded=True, use_reloader=False)
    except Exception as e:
        print(f"[错误] Flask 启动失败: {e}")
        raise
