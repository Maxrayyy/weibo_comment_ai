# V5 技术方案 — Docker容器化部署

## 架构设计

### 1. 镜像结构
使用单一Dockerfile + docker-compose多服务模式：

```
Dockerfile          # 统一基础镜像（Python + Chrome + 依赖）
docker-compose.yml  # 4个服务定义
.dockerignore       # 排除不需要的文件
```

### 2. 基础镜像层次
```
python:3.11-slim
  ├── 安装 Google Chrome (stable)
  ├── 安装 Python依赖 (requirements.txt)
  └── 复制项目代码
```

### 3. Chrome/ChromeDriver安装方案
在Dockerfile中直接安装 google-chrome-stable，然后使用 `webdriver-manager` 自动下载匹配的ChromeDriver。

代码中需要改造：
- `login_manager.py` — 使用webdriver-manager的 `ChromeDriverManager().install()` 替代硬编码路径
- `oauth_manager.py` — 同上
- `weibo_scraper.py` — 同上

### 4. 代码改造点

#### 4.1 ChromeDriver路径（3个文件）
```python
# Before（硬编码Windows路径）
chromedriver_path = os.path.join(os.path.expanduser("~"), ".wdm", "drivers", "chromedriver", "win64", ...)
service = Service(chromedriver_path)

# After（自动检测）
from webdriver_manager.chrome import ChromeDriverManager
service = Service(ChromeDriverManager().install())
```

#### 4.2 Docker环境检测
添加环境变量 `DOCKER_ENV=1`，在Docker中：
- 跳过 `manual_login()`，要求预置cookies.json
- 跳过 `_get_authorization_code()` 的浏览器弹窗，要求预置oauth_token.json
- 自动使用headless模式

#### 4.3 User-Agent
将Windows UA改为通用UA，或使用Linux UA。

### 5. docker-compose服务定义
```yaml
services:
  weibo-friend-group:
    build: .
    command: python run_friend_group.py
    volumes: [data, config, .env]
    restart: unless-stopped

  weibo-reply:
    command: python run_reply.py
    ...

  weibo-chaohua:
    command: python run_chaohua.py
    ...

  weibo-timeline:
    command: python main.py
    ...
```

### 6. 数据卷映射
```
./data:/app/data           # cookies, token, records
./config:/app/config       # config.yaml, prompts.yaml
./.env:/app/.env           # 环境变量
./logs:/app/logs           # 日志输出
```