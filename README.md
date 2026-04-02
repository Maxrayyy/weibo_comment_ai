# 微博全自动评论系统

基于 Selenium + 微博官方API + Qwen大模型 的全自动微博评论机器人。支持时间线评论、好友圈评论、超话功能、自动回复评论等多种模式。

## 功能特性

### 核心功能
- **智能评论生成** — 使用Qwen大模型根据微博内容生成自然、多样的评论
- **多模态识别** — 支持识别微博图片内容，生成更贴合的评论
- **表情支持** — 自动获取微博表情列表，评论中自然嵌入表情
- **自动回复评论** — 监控收到的评论并自动生成回复（支持楼中楼）

### 运行模式
| 模式 | 入口文件 | 说明 |
|------|---------|------|
| 时间线模式 | `main.py` | 通过API抓取首页时间线，评论目标用户的微博 |
| 好友圈模式 | `run_friend_group.py` | 通过Selenium抓取好友圈分组页面，评论好友微博 |
| 超话模式 | `run_chaohua.py` | 超话签到、发帖、评论 |
| 回复模式 | `run_reply.py` | 自动回复自己微博下收到的评论 |

### 策略与风控
- **白名单/黑名单** — 灵活控制评论范围
- **随机间隔轮询** — 模拟真人行为
- **每日上限** — 各模式独立计数
- **工作时段** — 可配置运行时间段
- **评论去重** — 避免重复评论和雷同内容
- **Cookie自动管理** — 首次手动登录，之后自动维持

## 项目结构

```
weibo_comment_ai/
├── config/
│   ├── config.yaml           # 主配置文件
│   └── prompts.yaml          # 评论风格模板
├── src/
│   ├── auth/                 # 登录与OAuth认证
│   ├── scraper/              # 微博页面抓取与解析
│   ├── comment/              # AI评论生成与发布
│   ├── reply/                # 自动回复评论模块
│   ├── chaohua/              # 超话功能（签到/发帖/评论）
│   ├── emotion/              # 微博表情管理
│   ├── scheduler/            # 多任务调度器
│   ├── storage/              # 评论/回复记录存储
│   └── utils/                # 日志、配置加载、IP获取
├── data/                     # 运行时数据（Cookie、Token、记录、表情缓存）
├── logs/                     # 运行日志
├── docs/                     # 各版本设计文档
├── test/                     # 调试和测试脚本
├── main.py                   # 时间线模式入口
├── run_friend_group.py       # 好友圈模式入口
├── run_chaohua.py            # 超话模式入口
├── run_reply.py              # 回复模式入口
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

Selenium需要Chrome浏览器，ChromeDriver会由 `webdriver-manager` 自动管理。

## 配置

### 环境变量

创建 `.env` 文件：

```bash
WEIBO_APP_KEY=你的微博App Key
WEIBO_APP_SECRET=你的微博App Secret
DASHSCOPE_API_KEY=你的Qwen API Key
```

### 微博开放平台

1. 访问 [open.weibo.com](https://open.weibo.com) 注册开发者应用
2. 在应用的「高级信息」中设置授权回调页为：`https://api.weibo.com/oauth2/default.html`

### 主要配置

编辑 `config/config.yaml`：

```yaml
# 评论策略
strategy:
  mode: "whitelist"           # whitelist 或 blacklist
  whitelist: [1234567890]     # 要评论的好友UID列表
  daily_limit: 50             # 每日评论上限
  skip_repost: true           # 跳过转发微博

# 轮询间隔（秒）
timing:
  poll_min: 20
  poll_max: 50

# 好友圈配置
friend_group:
  enabled: true
  gid: "你的好友圈分组ID"

# 自动回复评论配置
reply:
  enabled: true
  daily_limit: 30
  poll_min: 60
  poll_max: 180

# 超话配置
chaohua:
  enabled: false
```

### 评论风格

编辑 `config/prompts.yaml` 自定义评论风格。内置三种风格：

- `weibo_base` — 微博评论底座（默认，自然接话风格）
- `weibo_friend` — 朋友圈风格（轻松机灵，冷幽默）
- `weibo_reply` — 博主回复评论（回复模式专用）

## 使用

```bash
# 时间线模式（API抓取首页微博并评论）
python main.py

# 好友圈模式（Selenium抓取好友圈并评论）
python run_friend_group.py

# 超话模式（签到/发帖/评论）
python run_chaohua.py

# 回复模式（自动回复收到的评论）
python run_reply.py
```

**首次运行：**
1. 程序会打开Chrome浏览器，请手动完成微博登录（包括验证码）
2. 登录成功后，程序自动保存Cookie
3. 接着会弹出OAuth授权页面，点击授权即可
4. 之后程序进入自动轮询模式

**后续运行：**
- 程序自动加载已保存的Cookie和Token
- 过期时会提示重新登录/授权

**退出：** `Ctrl+C` 优雅退出

## 注意事项

- 微博 access_token 有效期仅 **2小时**，过期后需重新OAuth授权
- Cookie有效期通常较长，但也可能过期需重新登录
- 建议初期用白名单模式测试 1-2 个好友，稳定后再扩大范围
- 合理设置每日评论上限和轮询间隔，避免触发风控
- 回复模式需要保持Selenium浏览器实例运行

## 技术栈

- **Python 3.10+**
- **Selenium** — 浏览器自动化（好友圈/超话/评论收件箱抓取）
- **BeautifulSoup4** — HTML解析
- **Qwen API** (OpenAI SDK兼容) — AI评论/回复生成（支持多模态）
- **微博开放平台API** — 评论发布、回复发送
- **APScheduler** — 多任务调度

## License

MIT
