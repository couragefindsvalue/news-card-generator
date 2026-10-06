# 使用 Python 3.11 的轻量级镜像作为基础环境
FROM python:3.11-slim

# 设置容器内的工作目录
WORKDIR /app

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目中的所有文件到容器内
COPY . .

# 暴露 8080 端口（Render 会动态分配端口，这里主要作为声明）
EXPOSE 8080

# 启动命令：使用 Gunicorn 作为生产服务器运行 Flask 应用
# 注意：`app:app` 指向你的 `app.py` 文件中的 `app` 实例
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT app:app"]