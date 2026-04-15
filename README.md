# 微博全自动评论系统

基于 Selenium + AI大模型 的全自动微博评论机器人。支持好友圈评论、超话签到/发帖/评论、自动回复评论等多种模式，通过浏览器自动化模拟真人操作。

## 功能特性

### 核心功能
- **智能评论生成** — 使用 DeepSeek / Qwen 大模型根据微博内容生成自然、多样的评论
- **多模态识别** — 支持识别微博图片内容，生成更贴合的评论（Qwen-VL）
- **表情支持** — 自动获取微博表情列表，评论中自然嵌入表情
- **自动回复评论** — 监控收到的评论并自动生成回复（支持楼中楼）

### 运行模式
| 模式 | 入口文件 | 说明 | 状态 |
|------|---------|------|------|
| 好友圈模式 | `run_friend_group.py` | Selenium抓取好友圈分组页面，评论好友微博 | **主力模式** |
| 回复模式 | `run_reply.py` | 自动回复自己微博下收到的评论 | 运行中 |
| 超话模式 | `run_chaohua.py` | 超话签到、发帖、评论 | 运行中 |
| 时间线模式 | `main.py` | 通过API抓取首页时间线并评论 | 已停用 |

> 时间线模式因微博开放API配额有限已停用，改用好友圈Selenium模式替代。

### 策略与风控
- **白名单/黑名单** — 灵活控制评论范围
- **随机间隔轮询** — 模拟真人行为
- **每日上限** — 各模式独立计数
- **工作时段** — 可配置运行时间段
- **评论去重** — 避免重复评论和雷同内容
- **Cookie自动管理** — 首次手动登录，之后自动维持
- **限流检测** — 触发403/414自动冷却10分钟
- **健康检查** — 连续失败自动停止服务，防止无效重试
- **邮件告警** — 超话签到失败、服务异常时自动发送邮件通知

## 技术架构

```
┌─────────────────────────────────────────────────┐
│                  运行模式入口                      │
│  run_friend_group.py │ run_reply.py │ run_chaohua.py │
└────────┬────────────┬──────────────┬─────────────┘
         │            │              │
    ┌────▼────┐  ┌────▼────┐  ┌─────▼─────┐
    │好友圈抓取│  │评论收件箱│  │ 超话客户端  │
    │Selenium │  │Selenium │  │Selenium+API│
    └────┬────┘  └────┬────┘  └─────┬──────┘
         │            │              │
    ┌────▼────────────▼──────────────▼──────┐
    │          AI 评论/回复生成               │
    │  DeepSeek(纯文字) + Qwen-VL(图片微博)  │
    └────────────────┬──────────────────────┘
                     │
    ┌────────────────▼──────────────────────┐
    │        评论发布 (Cookie AJAX)           │
    │  weibo.com/ajax/comments/create        │
    └────────────────────────────────────────┘
```

### 微博交互方式
| 功能 | 方式 | 说明 |
|------|------|------|
| 微博抓取 | Selenium + BeautifulSoup | 浏览器自动化解析页面DOM |
| 评论发布 | Cookie AJAX | 通过Selenium执行XHR请求 |
| 回复发送 | UI模拟 | Selenium模拟点击回复按钮和输入 |
| 获取UID | OAuth2 API | `api.weibo.com/2/account/get_uid` |
| 获取表情 | OAuth2 API | `api.weibo.com/2/emotions` |

> 微博开放平台API仅用于获取用户UID和表情列表两个辅助功能，核心业务全部通过Selenium浏览器自动化完成。

## 项目结构

```
weibo_comment_ai/
├── config/
│   ├── config.yaml           # 主配置文件
│   ├── config.prod.yaml      # 生产环境配置（可选，存在时自动加载覆盖）
│   └── prompts.yaml          # 评论风格模板
├── src/
│   ├── auth/                 # 登录（Cookie）与OAuth2认证
│   ├── scraper/              # 微博页面抓取与解析
│   ├── comment/              # AI评论生成与发布
│   ├── reply/                # 自动回复评论模块
│   ├── chaohua/              # 超话功能（签到/发帖/评论）
│   ├── emotion/              # 微博表情管理
│   ├── scheduler/            # APScheduler多任务调度
│   ├── storage/              # 评论/回复记录存储（JSON）
│   └── utils/                # 日志、配置加载、WebDriver管理、告警通知
├── data/                     # 运行时数据（Cookie、Token、记录、表情缓存）
├── logs/                     # 运行日志
├── docs/                     # 各版本设计文档
├── main.py                   # 时间线模式入口（已停用）
├── run_friend_group.py       # 好友圈模式入口
├── run_chaohua.py            # 超话模式入口
├── run_reply.py              # 回复模式入口
├── refresh_cookies.py        # Cookie刷新/重新登录工具
├── Dockerfile                # Docker镜像定义
├── docker-compose.yml        # 多服务编排（3个独立容器）
└── requirements.txt
```

## 安装

### 1. 克隆项目

```bash
git clone https://github.com/Maxrayyy/weibo_comment_ai.git
cd weibo_comment_ai
```

### 2. 创建虚拟环境

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

### 4. 安装Chrome浏览器

Selenium需要Chrome浏览器，ChromeDriver由 `webdriver-manager` 自动管理。

## 配置

### 环境变量

创建 `.env` 文件：

```bash
# 微博开放平台（用于获取UID和表情列表）
WEIBO_APP_KEY=你的微博App Key
WEIBO_APP_SECRET=你的微博App Secret

# AI大模型
DEEPSEEK_API_KEY=你的DeepSeek API Key      # 纯文字评论生成
DASHSCOPE_API_KEY=你的通义千问 API Key       # 图片微博多模态评论生成

# 邮件告警（可选）
NOTIFY_EMAIL_PASSWORD=你的SMTP授权码          # 163邮箱的SMTP授权码，非登录密码
```

### 微博开放平台

1. 访问 [open.weibo.com](https://open.weibo.com) 注册开发者应用
2. 在应用的「高级信息」中设置授权回调页为：`https://api.weibo.com/oauth2/default.html`

> 开放平台仅用于OAuth2授权获取UID和表情列表，不消耗评论/回复等核心API配额。

### 主要配置

编辑 `config/config.yaml`：

```yaml
# AI大模型（兼容OpenAI SDK的任意平台）
llm:
  text:                              # 纯文字微博
    api_key: "${DEEPSEEK_API_KEY}"
    base_url: "https://api.deepseek.com"
    model: "deepseek-chat"
  multimodal:                        # 有图片微博
    api_key: "${DASHSCOPE_API_KEY}"
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model: "qwen-vl-plus"

# 评论策略
strategy:
  mode: "whitelist"           # whitelist 或 blacklist
  whitelist: [1234567890]     # 要评论的好友UID列表
  daily_limit: 300            # 每日评论上限
  skip_repost: true           # 跳过转发微博

# 轮询间隔（秒）
timing:
  poll_min: 300
  poll_max: 600

# 好友圈配置
friend_group:
  enabled: true
  gid: "你的好友圈分组ID"

# 自动回复评论配置
reply:
  enabled: true
  daily_limit: 100
  poll_min: 100
  poll_max: 180
  blacklist: []               # 不自动回复的用户UID

# 超话配置
chaohua:
  enabled: false
  sign:
    enabled: true
    schedule: "08:00"         # 每日签到时间
  post:
    enabled: false
  comment:
    enabled: true
    daily_limit: 100

# 健康检查与告警
health:
  max_consecutive_failures: 6 # 连续失败N次后自动停止服务
  cookie_check_hours: 6       # Cookie有效性检查间隔（小时）

# 邮件告警通知
notify:
  enabled: true
  email:
    smtp_host: "smtp.163.com"
    smtp_port: 465
    sender: "xxx@163.com"
    password: "${NOTIFY_EMAIL_PASSWORD}"
    receiver: "xxx@163.com"

# 日志配置
logging:
  max_bytes: 524288           # 单文件最大 512KB
  backup_count: 2             # 保留备份数
```

### 评论风格

编辑 `config/prompts.yaml` 自定义评论风格。内置两种风格：

- `weibo_base` — 微博评论底座（默认，自然接话风格）
- `weibo_reply` — 回复评论（回复模式专用，支持博主回复和楼中楼回复两种场景）

## 使用

### 本地运行

```bash
# 好友圈模式（主力模式，Selenium抓取好友圈并评论）
python run_friend_group.py

# 回复模式（自动回复收到的评论）
python run_reply.py

# 超话模式（签到/发帖/评论）
python run_chaohua.py
```

**首次运行：**
1. 程序打开Chrome浏览器，请手动完成微博登录（包括验证码）
2. 登录成功后，程序自动保存Cookie到 `data/cookies.json`
3. 接着弹出OAuth授权页面，点击授权（获取UID用）
4. 之后程序进入自动轮询模式

**后续运行：**
- 程序自动加载已保存的Cookie和Token
- 过期时会提示重新登录/授权

**退出：** `Ctrl+C` 优雅退出

### Docker部署

```bash
# 构建并启动所有服务（好友圈 + 回复 + 超话）
docker compose up -d --build

# 查看日志
docker compose logs -f weibo-friend-group

# 查看所有服务状态
docker compose ps

# 停止所有服务
docker compose down
```

> Docker环境无法进行手动登录，需先在本地完成登录和OAuth授权，将 `data/cookies.json` 和 `data/oauth_token.json` 挂载到容器中。

### Cookie刷新

Cookie过期后所有服务会失败（好友圈XMLHttpRequest异常、超话登录失败、回复加载超时），此时需要刷新Cookie。

**方式一：使用刷新脚本（推荐）**

在本地开发机上运行：

```bash
python refresh_cookies.py
```

脚本会打开Chrome浏览器：
- 如果Cookie仍有效：自动刷新续期并保存
- 如果Cookie已过期：跳转登录页，手动登录后自动保存

**方式二：重新运行服务**

本地直接运行任意服务入口（如 `python run_friend_group.py`），首次会弹出登录窗口。

**更新到服务器：**

Cookie刷新后需要上传到服务器并重启容器：

```bash
# 上传Cookie到服务器
scp data/cookies.json ubuntu@你的服务器:/path/to/weibo_comment_ai/data/cookies.json

# SSH到服务器重启容器
ssh ubuntu@你的服务器
cd /path/to/weibo_comment_ai
docker compose restart
```

## 告警通知

系统在以下情况会发送邮件告警：
- 超话签到失败
- 连续多次轮询失败（由 `health.max_consecutive_failures` 控制）
- 浏览器session异常

收到告警邮件后，通常意味着Cookie已过期，需按上述流程刷新Cookie。

## 注意事项

- Cookie有效期通常为数天，过期后需通过 `refresh_cookies.py` 刷新或重新登录
- OAuth access_token 有效期仅 **2小时**，过期后需重新授权（仅影响UID获取和表情）
- 建议初期用白名单模式测试 1-2 个好友，稳定后再扩大范围
- 合理设置每日评论上限和轮询间隔，避免触发风控
- 回复模式通过UI模拟方式发送，支持楼中楼回复
- Docker容器配置了 `restart: unless-stopped`，异常退出会自动重启

## 技术栈

- **Python 3.10+**
- **Selenium** — 浏览器自动化（页面抓取、评论发布、回复发送）
- **BeautifulSoup4** — HTML解析
- **DeepSeek API** — 纯文字评论生成
- **Qwen-VL API** (通义千问) — 多模态评论生成（图片识别）
- **OpenAI SDK** — 统一的LLM调用接口（兼容DeepSeek、Dashscope）
- **APScheduler** — 多任务调度
- **Docker Compose** — 生产环境多服务编排

## License

MIT
