#!/usr/bin/env python3
"""
ColabMCP 使用示例

这个脚本展示了如何使用 ColabMCP 客户端远程控制 Google Colab。
"""

import sys
import os

# 添加 client 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'client'))

from colab_client import ColabMCPClient


def example_basic_usage():
    """基本使用示例"""
    # 替换为你的 ngrok URL
    url = "https://your-ngrok-url.ngrok-free.app"
    
    # 创建客户端
    client = ColabMCPClient(url)
    
    # 1. 健康检查
    print("=== 健康检查 ===")
    health = client.health_check()
    print(f"状态: {health.get('status')}")
    print(f"可用内存: {health.get('memory_available_gb')} GB")
    print()
    
    # 2. 探测环境
    print("=== 环境探测 ===")
    probe = client.probe_environment()
    print(f"Python: {probe.get('python_version')[:50]}...")
    print(f"已安装包: {probe.get('total_packages')} 个")
    print()
    
    # 3. 执行代码
    print("=== 执行代码 ===")
    result = client.execute_code("""
import numpy as np
import pandas as pd

# 创建数据
data = pd.DataFrame({
    'A': np.random.randn(100),
    'B': np.random.randn(100),
    'C': np.random.choice(['X', 'Y', 'Z'], 100)
})

print("数据预览:")
print(data.head())
print()
print("统计信息:")
print(data.describe())
""")
    
    if result.get("success"):
        print(result.get("stdout"))
    else:
        print(f"错误: {result.get('error')}")


def example_gpu_computation():
    """GPU 计算示例"""
    url = "https://your-ngrok-url.ngrok-free.app"
    client = ColabMCPClient(url)
    
    print("=== GPU 计算 ===")
    result = client.execute_code("""
import torch

print(f"CUDA 可用: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"GPU 名称: {torch.cuda.get_device_name(0)}")
    print(f"GPU 内存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    
    # 大规模矩阵运算
    print("\\n执行大规模矩阵运算...")
    x = torch.randn(5000, 5000, device='cuda')
    y = torch.randn(5000, 5000, device='cuda')
    
    import time
    start = time.time()
    z = torch.matmul(x, y)
    torch.cuda.synchronize()
    elapsed = time.time() - start
    
    print(f"矩阵乘法耗时: {elapsed:.4f} 秒")
    print(f"结果形状: {z.shape}")
    print(f"GPU 内存使用: {torch.cuda.memory_allocated() / 1024**2:.1f} MB")
else:
    print("GPU 不可用，使用 CPU")
    import numpy as np
    x = np.random.randn(5000, 5000)
    y = np.random.randn(5000, 5000)
    z = np.matmul(x, y)
    print(f"结果形状: {z.shape}")
""")
    
    if result.get("success"):
        print(result.get("stdout"))
    else:
        print(f"错误: {result.get('error')}")


def example_machine_learning():
    """机器学习示例"""
    url = "https://your-ngrok-url.ngrok-free.app"
    client = ColabMCPClient(url)
    
    print("=== 机器学习 ===")
    result = client.execute_code("""
from sklearn.datasets import load_iris, load_wine
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, classification_report
import pandas as pd

# 加载数据
data = load_wine()
X, y = data.data, data.target
feature_names = data.feature_names

print(f"数据集: Wine")
print(f"样本数: {len(X)}")
print(f"特征数: {len(feature_names)}")
print()

# 分割数据
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 比较多个模型
models = {
    'Random Forest': RandomForestClassifier(n_estimators=100, random_state=42),
    'Gradient Boosting': GradientBoostingClassifier(random_state=42),
    'SVM': SVC(random_state=42)
}

print("模型比较 (5折交叉验证):")
print("-" * 50)

results = []
for name, model in models.items():
    cv_scores = cross_val_score(model, X_train, y_train, cv=5)
    model.fit(X_train, y_train)
    test_acc = accuracy_score(y_test, model.predict(X_test))
    
    results.append({
        'Model': name,
        'CV Mean': cv_scores.mean(),
        'CV Std': cv_scores.std(),
        'Test Acc': test_acc
    })
    
    print(f"{name:20s} | CV: {cv_scores.mean():.4f} ± {cv_scores.std():.4f} | Test: {test_acc:.4f}")

print()
print("最佳模型:")
best = max(results, key=lambda x: x['Test Acc'])
print(f"  {best['Model']} (Test Acc: {best['Test Acc']:.4f})")
""")
    
    if result.get("success"):
        print(result.get("stdout"))
    else:
        print(f"错误: {result.get('error')}")


def example_data_visualization():
    """数据可视化示例（生成 base64 图片）"""
    url = "https://your-ngrok-url.ngrok-free.app"
    client = ColabMCPClient(url)
    
    print("=== 数据可视化 ===")
    result = client.execute_code("""
import matplotlib.pyplot as plt
import numpy as np
import base64
from io import BytesIO

# 设置非交互式后端
plt.switch_backend('Agg')

# 创建图表
fig, axes = plt.subplots(2, 2, figsize=(10, 8))

# 1. 折线图
x = np.linspace(0, 10, 100)
axes[0, 0].plot(x, np.sin(x), label='sin(x)')
axes[0, 0].plot(x, np.cos(x), label='cos(x)')
axes[0, 0].set_title('三角函数')
axes[0, 0].legend()
axes[0, 0].grid(True)

# 2. 直方图
data = np.random.randn(1000)
axes[0, 1].hist(data, bins=30, edgecolor='black', alpha=0.7)
axes[0, 1].set_title('正态分布')

# 3. 散点图
x = np.random.randn(100)
y = x + np.random.randn(100) * 0.5
axes[1, 0].scatter(x, y, alpha=0.6)
axes[1, 0].set_title('散点图')
axes[1, 0].set_xlabel('X')
axes[1, 0].set_ylabel('Y')

# 4. 柱状图
categories = ['A', 'B', 'C', 'D', 'E']
values = np.random.randint(10, 100, 5)
axes[1, 1].bar(categories, values, color='steelblue', edgecolor='black')
axes[1, 1].set_title('柱状图')

plt.tight_layout()

# 转换为 base64
buffer = BytesIO()
plt.savefig(buffer, format='png', dpi=100)
buffer.seek(0)
img_base64 = base64.b64encode(buffer.read()).decode()
plt.close()

print(f"图表已生成!")
print(f"Base64 长度: {len(img_base64)} 字符")
print(f"\\n前 100 字符: {img_base64[:100]}...")
print(f"\\n完整 base64 可用于: <img src=\\"data:image/png;base64,{img_base64[:50]}...\\">")
""")
    
    if result.get("success"):
        print(result.get("stdout"))
    else:
        print(f"错误: {result.get('error')}")


def example_variable_persistence():
    """变量持久化示例"""
    url = "https://your-ngrok-url.ngrok-free.app"
    client = ColabMCPClient(url)
    
    print("=== 变量持久化 ===")
    
    # 第一次执行：创建变量
    print("1. 创建变量...")
    result1 = client.execute_code("""
import numpy as np
import pandas as pd

# 创建一些变量
data = np.random.randn(100, 5)
df = pd.DataFrame(data, columns=['A', 'B', 'C', 'D', 'E'])
model_data = {'X': data, 'df': df}

print(f"创建了变量: data, df, model_data")
print(f"data shape: {data.shape}")
print(f"df shape: {df.shape}")
""")
    print(result1.get("stdout", ""))
    
    # 查看变量
    print("\n2. 查看存储的变量...")
    vars_result = client.list_variables()
    print(f"变量数量: {vars_result.get('count', 0)}")
    for name, info in vars_result.get('variables', {}).items():
        print(f"  {name}: {info}")
    
    # 第二次执行：使用之前的变量
    print("\n3. 使用之前的变量...")
    result2 = client.execute_code("""
# 使用之前创建的 df
print("使用之前创建的 DataFrame:")
print(df.describe())
""")
    print(result2.get("stdout", ""))
    
    # 清理
    print("\n4. 清理内存...")
    cleanup_result = client.cleanup()
    print(f"清理结果: {cleanup_result.get('message')}")


if __name__ == "__main__":
    print("=" * 60)
    print("ColabMCP 使用示例")
    print("=" * 60)
    print()
    print("请将 URL 替换为你的 ngrok URL 后运行示例")
    print()
    
    # 取消注释以运行示例
    # example_basic_usage()
    # example_gpu_computation()
    # example_machine_learning()
    # example_data_visualization()
    # example_variable_persistence()
    
    print("可用示例:")
    print("  - example_basic_usage()        # 基本使用")
    print("  - example_gpu_computation()    # GPU 计算")
    print("  - example_machine_learning()   # 机器学习")
    print("  - example_data_visualization() # 数据可视化")
    print("  - example_variable_persistence() # 变量持久化")
