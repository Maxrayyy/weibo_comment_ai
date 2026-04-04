FROM python:3.11-slim

# 使用清华 Debian 镜像源加速
RUN sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources

# 安装 Google Chrome 和必要的系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    fonts-wqy-zenhei \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-linux-signing-key.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux-signing-key.gpg] https://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    google-chrome-stable \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先安装 Python 依赖（利用 Docker 缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 预下载 ChromeDriver（构建时完成，运行时不再需要网络下载）
RUN python -c "from webdriver_manager.chrome import ChromeDriverManager; ChromeDriverManager().install()"

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
