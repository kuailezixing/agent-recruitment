# 1. 基础镜像：Python 3.11 精简版
FROM python:3.11-slim

# 2. 设置工作目录
WORKDIR /app

# 3. 安装系统依赖（jieba 编译需要 gcc，虽然这里是纯 Python，但预防万一）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 4. 先复制依赖文件，安装依赖（利用 Docker 缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 复制项目代码
COPY . .

# 6. 暴露端口
EXPOSE 8000

# 7. 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]