FROM registry.cn-hangzhou.aliyuncs.com/aliyun.com/python:3.12.11-alpine3.22

# 设置工作目录
WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口（FastAPI 默认运行在 8000 端口）
EXPOSE 8000

# 启动命令：使用 Uvicorn 运行 FastAPI 应用
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]