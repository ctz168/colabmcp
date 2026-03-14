# ModelScope 创空间创建教程

## 📋 创建步骤

### 第一步：登录 ModelScope
访问 https://modelscope.cn 并登录（可以用 GitHub 或阿里云账号）

### 第二步：创建创空间
1. 点击右上角 **「创建」** → **「创空间」**
2. 填写信息：
   - **名称**: `colabmcp`（或你喜欢的名字）
   - **可见性**: 公开
   - **SDK**: 选择 **Gradio**
3. 点击 **「创建」**

### 第三步：上传文件

创建后会进入创空间页面，有两种方式上传文件：

#### 方式一：网页上传（简单）
1. 在创空间页面点击 **「文件」** 标签
2. 点击 **「上传文件」**
3. 上传以下文件：
   - `ms_deploy.json`（配置文件）
   - `app.py`（服务器代码）

#### 方式二：Git 上传
```bash
# 克隆你的创空间
git clone https://www.modelscope.cn/studios/你的用户名/你的空间名.git

# 进入目录
cd 你的空间名

# 复制文件
cp ms_deploy.json ./
cp app.py ./

# 提交推送
git add .
git commit -m "Add MCP server"
git push
```

### 第四步：启动服务
1. 在创空间页面点击 **「运行」**
2. 等待服务启动
3. 获取公网 URL（页面顶部显示）

---

## 📁 需要的文件

### ms_deploy.json（配置文件）
```json
{
  "$schema": "https://modelscope.cn/api/v1/studio/deploy/schema",
  "type": "gradio",
  "port": 7860,
  "resource": "free",
  "cpu": 2,
  "memory": "16GB"
}
```

### app.py（服务器代码）
见 `modelscope_mcp_server.ipynb` 中生成的 `mcp_server.py`，重命名为 `app.py`

---

## 🔗 公网 URL

创建成功后，公网 URL 格式为：
```
https://你的用户名-空间名.modelscope.cn
```

例如：
```
https://ctz168-colabmcp.modelscope.cn
```

---

## ⚠️ 注意事项

1. **端口必须是 7860** - ModelScope 固定端口
2. **免费资源限制** - 2vCPU / 16GB RAM
3. **长时间不用会休眠** - 重新访问会自动激活
