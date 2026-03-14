#!/usr/bin/env python3
"""
ColabMCP Server - ModelScope 版本
直接运行在 ModelScope 创空间，无需 ngrok
"""

import os
import sys
import json
import time
import traceback
import subprocess
import gc
import threading
from flask import Flask, request, jsonify

try:
    import psutil
except ImportError:
    subprocess.run(['pip', 'install', 'psutil', '-q'], check=True)
    import psutil

# 全局变量
runtime_variables = {}
start_time = time.time()
execution_lock = threading.Lock()

# 创建 Flask 应用
app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "name": "ColabMCP Server (ModelScope)",
        "version": "1.1.0",
        "status": "running",
        "platform": "ModelScope",
        "endpoints": ["/health", "/probe", "/execute", "/variables", "/files", "/cleanup"]
    })

@app.route('/health', methods=['GET'])
def health_check():
    mem = psutil.virtual_memory()
    return jsonify({
        "status": "ok",
        "platform": "ModelScope",
        "uptime_minutes": round((time.time() - start_time) / 60, 2),
        "memory_available_gb": round(mem.available / (1024**3), 2),
        "memory_total_gb": round(mem.total / (1024**3), 2),
        "memory_used_pct": round(mem.percent, 2),
        "gpu_available": _check_gpu()
    })

@app.route('/probe', methods=['GET'])
def probe_environment():
    gpu_info = ""
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.free', '--format=csv'], 
                              capture_output=True, text=True, timeout=10)
        gpu_info = result.stdout
    except:
        gpu_info = "No GPU available"
    
    installed_packages = []
    try:
        result = subprocess.run(['pip', 'list', '--format=freeze'], capture_output=True, text=True, timeout=30)
        for line in result.stdout.split('\n'):
            if '==' in line:
                installed_packages.append(line.strip())
    except:
        pass
    
    mem = psutil.virtual_memory()
    
    return jsonify({
        "gpu_info": gpu_info,
        "memory_total_gb": round(mem.total / (1024**3), 2),
        "memory_available_gb": round(mem.available / (1024**3), 2),
        "python_version": sys.version,
        "installed_packages": installed_packages[:100],
        "total_packages": len(installed_packages)
    })

@app.route('/execute', methods=['POST'])
def execute_code():
    """执行 Python 代码，带错误隔离"""
    if not execution_lock.acquire(blocking=False):
        return jsonify({
            "success": False,
            "error": "另一个代码正在执行中，请稍后重试"
        })
    
    try:
        data = request.get_json()
        code = data.get('code', '')
        timeout = min(data.get('timeout', 300), 600)
        
        if not code:
            return jsonify({"success": False, "error": "No code provided"})
        
        exec_globals = {'__builtins__': __builtins__, **runtime_variables}
        exec_locals = {}
        
        from io import StringIO
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = captured_stdout = StringIO()
        sys.stderr = captured_stderr = StringIO()
        
        start_exec_time = time.time()
        
        try:
            exec(code, exec_globals, exec_locals)
            
            for key, value in exec_locals.items():
                if not key.startswith('_'):
                    try:
                        json.dumps({key: str(type(value))})
                        runtime_variables[key] = value
                    except:
                        pass
            
            return jsonify({
                "success": True,
                "stdout": captured_stdout.getvalue(),
                "stderr": captured_stderr.getvalue(),
                "execution_time_sec": round(time.time() - start_exec_time, 3),
                "variables": list(exec_locals.keys())
            })
            
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc(),
                "stdout": captured_stdout.getvalue(),
                "stderr": captured_stderr.getvalue(),
                "execution_time_sec": round(time.time() - start_exec_time, 3)
            })
        
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"服务器内部错误: {str(e)}",
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        })
    
    finally:
        execution_lock.release()

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
                except:
                    pass
            vars_info[key] = var_info
        except:
            vars_info[key] = {"type": str(type(value).__name__)}
    
    return jsonify({"variables": vars_info, "count": len(vars_info)})

@app.route('/files', methods=['GET'])
def list_files():
    files = []
    work_dir = os.getcwd()
    try:
        for f in os.listdir(work_dir):
            path = os.path.join(work_dir, f)
            try:
                size = os.path.getsize(path)
                files.append({
                    "name": f,
                    "path": path,
                    "size_bytes": size,
                    "size_readable": f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/1024/1024:.1f} MB",
                    "is_dir": os.path.isdir(path)
                })
            except:
                pass
    except Exception as e:
        return jsonify({"error": str(e), "files": []})
    return jsonify({"files": files, "count": len(files)})

@app.route('/cleanup', methods=['POST'])
def cleanup():
    global runtime_variables
    runtime_variables = {}
    gc.collect()
    
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except:
        pass
    
    mem = psutil.virtual_memory()
    return jsonify({
        "success": True,
        "message": "Memory cleaned",
        "memory_available_gb": round(mem.available / (1024**3), 2)
    })

def _check_gpu():
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True, timeout=5)
        return result.returncode == 0
    except:
        return False

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 ColabMCP 服务器启动中 (ModelScope)")
    print("="*60)
    print("端口: 7860")
    print("版本: 1.1.0")
    print("="*60 + "\n")
    app.run(port=7860, host='0.0.0.0', threaded=True)
