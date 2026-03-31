# 微博全自动评论系统 — 设计文档

## 1. 项目概述

### 1.1 目标

构建一个全自动微博评论系统，通过监控用户关注好友的最新微博，使用AI大模型生成自然的评论内容，并自动发布评论。

### 1.2 核心需求

- 获取用户的完整关注列表
- 实时监控好友发布的新微博
- 使用Qwen大模型根据微博内容智能生成评论
- 自动发布评论到对应微博
- 模拟真人行为，避免被风控检测

### 1.3 技术路线

**混合方案**：Selenium浏览器自动化获取数据 + 微博官方API发布评论

选择理由：
- 微博官方API有严重限制（好友列表只返回授权本应用的用户，时间线只返回授权用户微博）
- Selenium可以绕过这些限制，获取完整的关注列表和好友最新微博
- 官方API发评论更稳定可靠，不易触发反爬机制

---

## 2. 微博开放平台API调研

### 2.1 核心API清单

| 接口 | URL | 方法 | 说明 |
|------|-----|------|------|
| OAuth2授权 | `https://api.weibo.com/oauth2/authorize` | GET | 请求用户授权Token |
| 获取Token | `https://api.weibo.com/oauth2/access_token` | POST | 获取access_token |
| 获取UID | `https://api.weibo.com/2/account/get_uid.json` | GET | 获取当前授权用户UID |
| 用户信息 | `https://api.weibo.com/2/users/show.json` | GET | 获取用户详细信息 |
| 关注列表 | `https://api.weibo.com/2/friendships/friends.json` | GET | 获取关注列表 |
| 关注ID列表 | `https://api.weibo.com/2/friendships/friends/ids.json` | GET | 获取关注用户ID列表 |
| 首页时间线 | `https://api.weibo.com/2/statuses/home_timeline.json` | GET | 获取关注用户最新微博 |
| 用户时间线 | `https://api.weibo.com/2/statuses/user_timeline.json` | GET | 获取指定用户微博 |
| 单条微博 | `https://api.weibo.com/2/statuses/show.json` | GET | 根据ID获取单条微博 |
| 微博计数 | `https://api.weibo.com/2/statuses/count.json` | GET | 批量获取转发/评论数 |
| 发表评论 | `https://api.weibo.com/2/comments/create.json` | POST | 评论一条微博 |
| 回复评论 | `https://api.weibo.com/2/comments/reply.json` | POST | 回复一条评论 |
| 评论列表 | `https://api.weibo.com/2/comments/show.json` | GET | 获取某条微博评论 |
| 频率限制 | `https://api.weibo.com/2/account/rate_limit_status.json` | GET | 查询API调用频率 |

### 2.2 关键API详细说明

#### 2.2.1 OAuth2认证流程

**步骤一：请求授权码**
```
GET https://api.weibo.com/oauth2/authorize
参数：
  - client_id: App Key
  - redirect_uri: 回调地址（需与应用注册时一致）
  - scope: 权限范围（可选）
  - state: 防CSRF参数（可选）
  - display: 终端类型 default/mobile
返回：重定向到回调地址，附带code参数
```

**步骤二：获取access_token**
```
POST https://api.weibo.com/oauth2/access_token
参数：
  - client_id: App Key
  - client_secret: App Secret
  - grant_type: "authorization_code"
  - code: 上一步获取的授权码
  - redirect_uri: 回调地址
返回：
  {
    "access_token": "ACCESS_TOKEN",
    "expires_in": 7200,       // 有效期2小时
    "remind_in": 7200,
    "uid": "1404376560"
  }
```

#### 2.2.2 发表评论接口（核心）

```
POST https://api.weibo.com/2/comments/create.json
必需参数：
  - access_token: OAuth授权令牌
  - id: 微博ID (int64)
  - comment: 评论内容（URLencode，不超过140汉字）
  - rip: 用户真实IP
可选参数：
  - comment_ori: 是否评论原微博（0否/1是，默认0）
返回：评论对象（包含评论ID、内容、作者信息、被评论微博信息）
```

#### 2.2.3 首页时间线接口

```
GET https://api.weibo.com/2/statuses/home_timeline.json
参数：
  - access_token: OAuth授权令牌
  - since_id: 返回ID大于此值的微博（用于增量获取）
  - max_id: 返回ID小于等于此值的微博
  - count: 每页数量（最大100，默认20）
  - page: 页码（默认1）
  - feature: 过滤类型（0全部/1原创/2图片/3视频/4音乐）
返回：
  {
    "statuses": [...],      // 微博对象数组
    "total_number": 100
  }
```

### 2.3 官方API关键限制

| 限制项 | 具体限制 | 影响 |
|--------|---------|------|
| Token有效期 | 仅2小时，无refresh_token | 需频繁重新授权 |
| 好友列表 | 只返回同样授权本应用的用户，每页最多5条 | **无法获取完整关注列表** |
| 时间线 | 只返回授权用户的微博 | **无法获取所有好友微博** |
| user_timeline | 最多返回5条（移动SDK10条） | 数据量严重不足 |
| 评论长度 | 不超过140汉字 | 需控制AI生成长度 |
| 频率限制 | 各接口有调用次数限制 | 需合理控制调用频率 |

### 2.4 为什么选择混合方案

由于上述API限制，纯API方案无法满足需求。混合方案的策略是：

- **数据获取层**：使用Selenium模拟浏览器访问微博网页版，可以获取完整的关注列表和所有好友微博
- **评论发布层**：使用官方API发布评论，因为API发评论比Selenium模拟点击更稳定可靠

---

## 3. 系统架构

### 3.1 架构图

```
┌─────────────────────────────────────────────────────┐
│                    主调度器 (Scheduler)                │
│              随机间隔轮询 (5~15分钟)                    │
└──────────┬──────────────┬──────────────┬────────────┘
           │              │              │
           ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
│  登录管理模块  │ │  微博抓取模块  │ │   评论发布模块    │
│ (Auth)       │ │ (Scraper)    │ │ (Commenter)      │
│              │ │              │ │                  │
│ · 首次手动登录 │ │ · Selenium   │ │ · Qwen AI生成评论 │
│ · Cookie持久化│ │   抓取好友微博 │ │ · 官方API发评论   │
│ · 过期检测    │ │ · 新微博检测   │ │ · 随机延迟发送    │
└──────────────┘ └──────────────┘ └──────────────────┘
           │              │              │
           ▼              ▼              ▼
┌─────────────────────────────────────────────────────┐
│                  配置管理 (Config)                     │
│  · 白名单/黑名单  · 评论风格prompt  · 频率参数          │
│  · API密钥       · 每日评论上限    · Cookie存储路径     │
└─────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────┐
│                  数据存储 (Storage)                    │
│  · 已评论微博记录(避免重复)  · Cookie  · 运行日志       │
└─────────────────────────────────────────────────────┘
```

### 3.2 模块说明

| 模块 | 技术选型 | 职责 |
|------|---------|------|
| **主调度器** | APScheduler | 随机间隔触发抓取和评论任务 |
| **登录管理** | Selenium + JSON | 首次手动登录，Cookie持久化存储，过期自动检测提醒 |
| **OAuth管理** | requests | 管理access_token的获取和刷新 |
| **微博抓取** | Selenium + BeautifulSoup | 抓取关注列表、好友最新微博，检测新微博 |
| **评论生成** | Qwen API (OpenAI SDK兼容) | 根据微博内容 + 配置的风格prompt生成自然评论 |
| **评论发布** | requests (微博API) | 通过OAuth2 API发布评论 |
| **配置管理** | PyYAML | 管理所有可配置项 |
| **数据存储** | JSON文件 | 记录已评论微博ID、Cookie、运行日志 |

---

## 4. 核心流程

### 4.1 登录与Cookie管理流程

```
程序启动
  │
  ├─ 检查本地Cookie文件是否存在
  │    │
  │    ├─ 存在 → 加载Cookie → 访问微博验证有效性
  │    │                         │
  │    │                         ├─ 有效 → 进入主循环
  │    │                         └─ 无效 → 触发重新登录
  │    │
  │    └─ 不存在 → 触发首次登录
  │
  └─ 首次/重新登录流程：
       1. Selenium打开微博登录页 (weibo.com/login)
       2. 控制台提示用户手动完成登录（处理验证码等）
       3. 检测登录成功（URL跳转/页面元素变化）
       4. 提取浏览器Cookie → 保存到本地JSON文件
       5. 同时通过OAuth授权页面获取access_token
```

### 4.2 微博抓取与新微博检测流程

```
每次轮询周期：
  │
  1. 加载Cookie到Selenium浏览器
  │
  2. 根据配置决定抓取范围：
  │    ├─ 白名单模式 → 逐个访问白名单用户主页
  │    └─ 黑名单模式 → 访问首页时间线，过滤黑名单用户
  │
  3. 解析页面，提取微博列表：
  │    · 微博ID (mid)
  │    · 发布者UID和昵称
  │    · 微博正文内容
  │    · 发布时间
  │    · 是否为转发微博
  │
  4. 与本地已评论记录对比 → 筛选出新微博
  │
  5. 将新微博加入待评论队列
```

### 4.3 AI评论生成 + 发布流程

```
待评论队列中取出一条微博
  │
  1. 构造Qwen API请求：
  │    · system prompt = 配置的评论风格
  │    · user prompt = "请对以下微博生成一条自然评论：{微博内容}"
  │
  2. 调用Qwen API → 获取评论文本
  │
  3. 评论合规检查：
  │    · 长度不超过140字
  │    · 不含敏感词
  │    · 不重复最近的评论
  │
  4. 随机延迟 (30秒 ~ 3分钟)
  │
  5. 调用微博API发布评论：
  │    POST https://api.weibo.com/2/comments/create.json
  │    参数: access_token, id(微博ID), comment(评论内容), rip
  │
  6. 记录已评论微博ID到本地存储
  │
  7. 检查今日评论数是否达到上限 → 达到则暂停至次日
```

---

## 5. 风控策略

| 策略 | 参数 | 说明 |
|------|------|------|
| 轮询间隔 | 5~15分钟随机 | 避免固定频率被检测 |
| 评论间延迟 | 30秒~3分钟随机 | 模拟真人打字时间 |
| 每日评论上限 | 默认50条，可配置 | 防止过度评论触发风控 |
| 工作时段 | 8:00~23:00，可配置 | 模拟真人作息时间 |
| 转发微博 | 默认跳过，可配置 | 只评论原创微博更自然 |
| 评论去重 | 记录已评论微博ID | 避免重复评论同一条微博 |
| 评论多样性 | AI生成 + prompt变化 | 每条评论都不同，避免模板化 |

---

## 6. 项目文件结构

```
weibo_comment_ai/
├── config/
│   ├── config.yaml              # 主配置文件
│   └── prompts.yaml             # 评论风格prompt模板库
├── src/
│   ├── __init__.py
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── login_manager.py     # Selenium手动登录 + Cookie管理
│   │   └── oauth_manager.py     # OAuth2 access_token管理
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── weibo_scraper.py     # Selenium抓取好友微博
│   │   └── parser.py            # BeautifulSoup解析微博内容
│   ├── comment/
│   │   ├── __init__.py
│   │   ├── ai_generator.py      # Qwen API评论生成
│   │   └── publisher.py         # 微博API发布评论
│   ├── scheduler/
│   │   ├── __init__.py
│   │   └── task_scheduler.py    # 随机间隔调度器
│   ├── storage/
│   │   ├── __init__.py
│   │   └── record_store.py      # 已评论记录 + 数据持久化
│   └── utils/
│       ├── __init__.py
│       └── logger.py            # 日志工具
├── data/
│   ├── cookies.json             # Cookie持久化存储
│   ├── commented_records.json   # 已评论微博记录
│   └── raw_data.json
├── logs/
│   └── app.log                  # 运行日志
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-03-31-weibo-auto-comment-design.md
├── main.py                      # 程序入口
├── requirements.txt             # Python依赖
└── README.md
```

---

## 7. 配置文件设计

### 7.1 主配置 (config/config.yaml)

```yaml
# 微博OAuth配置
weibo:
  app_key: "你的App Key"
  app_secret: "你的App Secret"
  redirect_uri: "https://api.weibo.com/oauth2/default.html"

# Qwen大模型配置
qwen:
  api_key: "你的Qwen API Key"
  model: "qwen-turbo"
  max_tokens: 150

# 评论策略配置
strategy:
  mode: "whitelist"               # whitelist 或 blacklist
  whitelist: []                   # 白名单用户UID列表
  blacklist: []                   # 黑名单用户UID列表
  daily_limit: 50                 # 每日评论上限
  skip_repost: true               # 跳过转发微博
  work_hours:
    start: 8                      # 工作开始时间
    end: 23                       # 工作结束时间

# 随机间隔配置（秒）
timing:
  poll_min: 300                   # 轮询最小间隔 5分钟
  poll_max: 900                   # 轮询最大间隔 15分钟
  comment_delay_min: 30           # 评论延迟最小 30秒
  comment_delay_max: 180          # 评论延迟最大 3分钟

# 默认评论风格
default_prompt: "friendly"        # 引用prompts.yaml中的风格名
```

### 7.2 评论风格模板 (config/prompts.yaml)

```yaml
friendly:
  name: "友好互动型"
  system_prompt: |
    你是一个微博用户，正在给好友的微博写评论。
    要求：自然、轻松、像朋友聊天一样。可以带点幽默感。
    评论长度控制在10-50字之间。不要使用hashtag。
    不要暴露自己是AI。

thoughtful:
  name: "走心评论型"
  system_prompt: |
    你是一个微博用户，正在给好友的微博写一条走心的评论。
    要求：认真回应微博内容，表达真诚的想法或感受。
    评论长度控制在20-80字之间。不要使用hashtag。
    不要暴露自己是AI。

brief:
  name: "简短捧场型"
  system_prompt: |
    你是一个微博用户，正在给好友的微博点赞留言。
    要求：简短有力，表示支持。如"太赞了"、"哈哈哈笑死"、"支持！"等。
    评论长度控制在3-15字之间。
    不要暴露自己是AI。
```

---

## 8. 依赖清单

```
requests          # HTTP请求
selenium          # 浏览器自动化
webdriver-manager # WebDriver管理
beautifulsoup4    # HTML解析
pyyaml            # YAML配置解析
apscheduler       # 任务调度
openai            # Qwen API（兼容OpenAI SDK）
```

---

## 9. 技术风险与应对

| 风险 | 概率 | 影响 | 应对方案 |
|------|------|------|---------|
| 微博网页版改版导致抓取失败 | 中 | 高 | 抽象解析层，页面结构变化时只需修改parser.py |
| Cookie过期导致抓取中断 | 高 | 中 | 自动检测Cookie有效性，过期时提醒用户重新登录 |
| access_token过期（2小时） | 高 | 中 | 每次评论前检查token有效性，过期自动重新授权 |
| 评论频率过高被风控 | 中 | 高 | 随机延迟+每日上限+工作时段限制 |
| Qwen API调用失败 | 低 | 低 | 重试机制，失败后跳过该微博 |
| Selenium浏览器被检测 | 中 | 中 | 使用undetected-chromedriver等反检测方案 |
