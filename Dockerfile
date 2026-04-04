FROM python:3.11-slim

# 使用清华 Debian 镜像源加速
RUN sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources

# 安装 Chromium 浏览器和 ChromeDriver（系统包，无需翻墙）
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    fonts-wqy-zenhei \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先安装 Python 依赖（利用 Docker 缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 复制项目代码
COPY src/ src/
COPY config/ config/
COPY main.py run_friend_group.py run_reply.py run_chaohua.py ./

# 创建数据和日志目录
RUN mkdir -p data logs

# 设置 Docker 环境标识
ENV DOCKER_ENV=1
ENV PYTHONUNBUFFERED=1

# 默认入口（由 docker-compose 覆盖）
CMD ["python", "main.py"]
