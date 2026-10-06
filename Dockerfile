# 使用 Python 3.11 的轻量级镜像作为基础环境
FROM python:3.11-slim

# 设置容器内的工作目录
WORKDIR /app

# 安装系统依赖：包括 OpenCV 需要的库以及中英文字体
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    fonts-dejavu-core \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目中的所有文件到容器内
COPY . .

# 暴露 8080 端口（Render 会动态分配端口）
EXPOSE 8080

# 启动命令：使用 Gunicorn 作为生产服务器运行 Flask 应用
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT app:app"]