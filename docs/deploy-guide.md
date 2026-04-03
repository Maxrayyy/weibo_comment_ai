# Linux 服务器部署指南（从零开始）

适用于全新的 Linux 云服务器（Ubuntu 22.04/24.04），通过 Docker 部署微博自动评论系统。

---

## 一、本地准备（Windows 端）

在部署到服务器之前，需要先在本地完成登录，生成认证文件。

### 1.1 本地运行一次，完成登录

```bash
cd weibo_comment_ai
python main.py
```

程序会弹出浏览器：
1. 手动完成微博登录（包括验证码）→ 自动保存 `data/cookies.json`
2. 弹出 OAuth 授权页面，点击授权 → 自动保存 `data/oauth_token.json`
3. 看到 "开始轮询" 后按 `Ctrl+C` 退出即可

确认 `data/` 目录下有这两个文件：
```
data/cookies.json
data/oauth_token.json
```

### 1.2 配置好 .env 和 config

确认以下文件配置正确：
- `.env` — 包含 `WEIBO_APP_KEY`、`WEIBO_APP_SECRET`、`DASHSCOPE_API_KEY`
- `config/config.yaml` — 白名单 UID、好友圈 GID、超话配置等

---

## 二、服务器环境准备

以下所有命令在服务器上执行。以 Ubuntu 为例。

### 2.1 连接服务器

```bash
ssh root@你的服务器IP
```

### 2.2 更新系统

```bash
apt update && apt upgrade -y
```

### 2.3 安装 Docker

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 启动 Docker 并设置开机自启
systemctl start docker
systemctl enable docker

# 验证安装
docker --version
```

### 2.4 安装 Docker Compose

Docker Engine 24+ 已内置 `docker compose`（V2），无需单独安装。验证：

```bash
docker compose version
```

如果提示找不到命令，手动安装：
```bash
apt install -y docker-compose-plugin
```

### 2.5 安装 Git

```bash
apt install -y git
```

---

## 三、部署项目

### 3.1 克隆代码

```bash
cd /opt
git clone https://github.com/Maxrayyy/weibo_comment_ai.git
cd weibo_comment_ai
```

### 3.2 上传认证文件

在**本地**执行（将 Windows 上生成的文件传到服务器）：

```bash
# 在本地 Windows 的 Git Bash 或 PowerShell 中执行
scp data/cookies.json root@你的服务器IP:/opt/weibo_comment_ai/data/
scp data/oauth_token.json root@你的服务器IP:/opt/weibo_comment_ai/data/
```

或者用其他方式（WinSCP、宝塔面板文件管理等）将这两个文件上传到服务器的 `/opt/weibo_comment_ai/data/` 目录。

### 3.3 创建 .env 文件

在服务器上创建：

```bash
cat > /opt/weibo_comment_ai/.env << 'EOF'
WEIBO_APP_KEY=你的App_Key
WEIBO_APP_SECRET=你的App_Secret
DASHSCOPE_API_KEY=你的Dashscope_Key
EOF
```

或者直接从本地上传：
```bash
scp .env root@你的服务器IP:/opt/weibo_comment_ai/
```

### 3.4 确认目录结构

```bash
ls -la /opt/weibo_comment_ai/data/
# 应该看到：
# cookies.json
# oauth_token.json

ls -la /opt/weibo_comment_ai/.env
# 应该存在

ls -la /opt/weibo_comment_ai/config/
# 应该看到：
# config.yaml
# prompts.yaml
```

---

## 四、构建镜像

```bash
cd /opt/weibo_comment_ai
docker compose build
```

首次构建需要几分钟（下载 Python 基础镜像 + Chrome + 依赖）。构建成功后会看到类似输出：

```
 => exporting to image
 => => naming to docker.io/library/weibo_comment_ai-weibo-friend-group
```

---

## 五、启动服务

### 5.1 按需启动单个服务

```bash
# 只启动好友圈评论
docker compose up -d weibo-friend-group

# 只启动自动回复
docker compose up -d weibo-reply

# 只启动超话签到/评论
docker compose up -d weibo-chaohua

# 只启动时间线评论
docker compose up -d weibo-timeline
```

### 5.2 启动全部服务

```bash
docker compose up -d
```

### 5.3 查看运行状态

```bash
# 查看所有容器状态
docker compose ps

# 查看某个服务的日志（实时跟踪）
docker compose logs -f weibo-friend-group

# 查看最近 100 行日志
docker compose logs --tail 100 weibo-reply
```

---

## 六、日常维护

### 6.1 停止服务

```bash
# 停止单个服务
docker compose stop weibo-friend-group

# 停止全部服务
docker compose down
```

### 6.2 重启服务

```bash
docker compose restart weibo-friend-group
```

### 6.3 更新代码

```bash
cd /opt/weibo_comment_ai
git pull
docker compose build
docker compose up -d
```

### 6.4 更新 Cookie（Cookie 过期时）

微博 Cookie 过期后，容器日志会提示 "Docker环境下无法手动登录"。处理方式：

1. 在本地 Windows 重新运行 `python main.py`，完成登录
2. 将新的 `data/cookies.json` 上传到服务器：
   ```bash
   scp data/cookies.json root@你的服务器IP:/opt/weibo_comment_ai/data/
   ```
3. 重启服务：
   ```bash
   docker compose restart
   ```

### 6.5 更新 OAuth Token（Token 过期时）

同理，在本地重新授权后上传：
```bash
scp data/oauth_token.json root@你的服务器IP:/opt/weibo_comment_ai/data/
docker compose restart
```

### 6.6 查看日志文件

```bash
# 容器日志
docker compose logs --tail 200 weibo-friend-group

# 项目日志文件（挂载到宿主机）
ls /opt/weibo_comment_ai/logs/
cat /opt/weibo_comment_ai/logs/weibo_comment_ai.log
```

### 6.7 清理磁盘空间

```bash
# 清理无用的 Docker 镜像
docker image prune -f

# 清理所有未使用的资源
docker system prune -f
```

---

## 七、修改配置

配置文件通过 volume 挂载，直接在服务器上编辑即可，无需重新构建镜像：

```bash
# 编辑主配置
vi /opt/weibo_comment_ai/config/config.yaml

# 编辑评论风格
vi /opt/weibo_comment_ai/config/prompts.yaml

# 修改后重启服务生效
docker compose restart
```

---

## 八、常见问题

### Q: 构建时 Chrome 下载失败？

国内服务器可能无法访问 Google 源。解决方案：

```bash
# 方案一：配置代理
export http_proxy=http://你的代理:端口
export https_proxy=http://你的代理:端口
docker compose build

# 方案二：使用国内镜像源（修改 Dockerfile，将 google chrome 替换为 chromium）
# 将 Dockerfile 中的 google-chrome-stable 安装部分替换为：
# RUN apt-get update && apt-get install -y chromium chromium-driver
```

### Q: 容器启动后立刻退出？

```bash
# 查看退出原因
docker compose logs weibo-friend-group
```

常见原因：
- `.env` 文件缺失或内容错误
- `data/cookies.json` 不存在
- `config/config.yaml` 配置有误

### Q: 如何只运行部分服务？

docker-compose.yml 中的服务完全独立，按需启动即可：
```bash
# 只跑好友圈 + 回复，不跑超话和时间线
docker compose up -d weibo-friend-group weibo-reply
```

### Q: 服务器重启后容器会自动启动吗？

会。docker-compose.yml 中已配置 `restart: unless-stopped`，只要 Docker 服务开机自启（步骤 2.3 已设置），容器会自动恢复运行。

### Q: 多个服务同时写 data/ 目录会冲突吗？

不会。`record_store.py` 对不同功能使用独立的记录字段（评论记录、回复记录、超话记录），互不干扰。