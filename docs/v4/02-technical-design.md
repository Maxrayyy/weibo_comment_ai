# V4 技术方案：自动回复评论

## 架构设计

### 新增模块

```
src/
├── reply/                          # 新增：回复模块
│   ├── reply_fetcher.py            # Selenium抓取评论收件箱
│   ├── reply_generator.py          # AI生成回复内容
│   └── reply_sender.py             # API发送回复
├── scraper/
│   └── parser.py                   # 新增 parse_comment_inbox() 解析器
run_reply.py                        # 新增：回复模式入口
```

### 整体流程

```
run_reply.py (入口)
  ↓
ReplyBot.init()
  ├─ 获取公网IP
  ├─ Cookie验证
  ├─ OAuth认证
  ├─ 获取自己的UID
  └─ 启动Selenium浏览器 (WeiboScraper)
  ↓
TaskScheduler 定时轮询
  ↓
ReplyBot.poll_and_reply()
  ├─ 1. Selenium抓取评论收件箱页面 (reply_fetcher)
  │     └─ GET https://www.weibo.com/comment/inbox
  │     └─ 滚动加载 + HTML解析 (parse_comment_inbox)
  ├─ 2. 过滤：跳过自己、已回复、空评论
  ├─ 3. 对每条评论：
  │     ├─ a. 上下文已从HTML中提取（微博原文 + 评论 + 父评论）
  │     ├─ b. AI生成回复 (reply_generator)
  │     ├─ c. 随机延迟
  │     └─ d. 发送回复 (reply_sender)
  │           └─ POST comments/reply.json
  └─ 4. 记录已回复
```

## 评论获取方案

> **方案变更说明**：最初设计使用 `comments/to_me.json` API 获取评论，但测试发现返回错误码 10014（Insufficient app permissions），应用缺少该接口权限。改为 Selenium 抓取评论收件箱页面。

### Selenium 抓取评论收件箱

**页面 URL**：`https://www.weibo.com/comment/inbox`

**页面结构**（每个评论卡片）：
```
div.wbpro-scroller-item          # 卡片容器
├── div._h3_ > a                 # 评论者昵称（href含UID）
├── div._from_ > a               # 时间（href含cid评论ID和微博bid）
├── div._wbtext_._textImg_       # 评论内容（楼中楼以"回复@xxx:"开头）
└── div._repeatbox_              # 引用区域
    ├── div._replyComment_       # 楼中楼被回复的评论
    │   ├── span._replyCname_    # 被回复者昵称
    │   └── span                 # 被回复的评论内容
    └── div.feed-card-repost     # 原微博卡片
        ├── h4._title_           # 博主昵称
        └── div._messText_       # 微博原文
```

**关键提取字段**：

| 字段 | CSS选择器 | 提取方式 |
|------|---------|--------|
| 评论ID | `div._from_ > a` | URL中的 `cid` 参数 |
| 评论者UID | `div._h3_ > a` | URL中的 `/u/数字` |
| 评论者昵称 | `div._h3_ > a` | 文本内容 |
| 评论内容 | `div._wbtext_._textImg_` | 文本（楼中楼去掉"回复@xxx:"前缀） |
| 微博ID | `div._from_ > a` | URL中的bid → `bid_to_mid()` 转换 |
| 微博原文 | `div._messText_` | 文本内容 |
| 被回复评论 | `div._replyComment_ > span` | 文本内容（楼中楼场景） |
| 评论时间 | `div._from_ > a` | 文本内容 |

### 解析器

在 `src/scraper/parser.py` 中新增 `parse_comment_inbox(html)` 函数，返回统一格式的评论列表。

## 回复发送

**接口**：`POST https://api.weibo.com/2/comments/reply.json`

**参数**：
| 参数 | 类型 | 说明 |
|------|------|------|
| access_token | string | OAuth token |
| id | int64 | 微博ID |
| cid | int64 | 要回复的评论ID |
| comment | string | 回复内容，不超过140字 |
| without_mention | int | 1-不自动加@，0-自动加@ |
| comment_ori | int | 1-同时评论到微博，0-不评论 |
| rip | string | 用户真实IP |

**返回**：成功返回评论对象（含id），失败返回error_code。

## 配置方案

### config.yaml 新增

```yaml
reply:
  enabled: true
  daily_limit: 30
  poll_min: 60
  poll_max: 180
  reply_delay_min: 5
  reply_delay_max: 15
  prompt: "weibo_reply"
```

### prompts.yaml 新增

新增 `weibo_reply` prompt，特点：
- 身份是微博博主，回复别人对自己微博的评论
- 需要结合微博原文上下文
- 针对性回复评论内容
- 保持友好、自然、口语化

### config_loader.py 新增属性

```python
# reply 配置属性
reply_enabled -> bool
reply_daily_limit -> int
reply_poll_min -> int
reply_poll_max -> int
reply_delay_min -> int
reply_delay_max -> int
reply_prompt_name -> str
```

## 存储方案

### record_store.py 新增

在 `commented_records.json` 中新增：

```json
{
  "replied": {
    "评论ID": {
      "reply_text": "回复内容",
      "weibo_mid": "微博ID",
      "comment_user": "评论者昵称",
      "time": "2025-01-01 12:00:00",
      "reply_cid": "回复的评论ID"
    }
  },
  "reply_daily_counts": {
    "2025-01-01": 5
  },
  "reply_since_id": 0
}
```

**新增方法**：
- `is_replied(comment_id)` - 是否已回复
- `add_reply_record(comment_id, reply_text, weibo_mid, comment_user, reply_cid)` - 记录回复
- `get_reply_today_count()` - 今日回复数
- `get_reply_since_id()` / `set_reply_since_id(since_id)` - 增量拉取游标（Selenium模式下作为备用）

## 模块详细设计

### reply_fetcher.py

```python
COMMENT_INBOX_URL = "https://www.weibo.com/comment/inbox"

def fetch_comments_to_me(driver, scroll_times=2):
    """
    通过Selenium抓取评论收件箱页面，获取收到的评论列表。

    参数：
        driver: Selenium WebDriver 实例
        scroll_times: 页面滚动次数

    返回：评论列表 [{
        "comment_id": str,
        "comment_text": str,
        "comment_user_id": str,
        "comment_user_name": str,
        "weibo_mid": str,
        "weibo_text": str,
        "reply_comment_text": str or None,
        "reply_comment_user": str or None,
        "created_at": str,
    }, ...]
    """
```

### reply_generator.py

```python
def generate_reply(weibo_text, comment_text, reply_comment_text=None, max_retries=3):
    """
    根据微博内容和评论内容生成回复

    参数：
        weibo_text: 微博原文
        comment_text: 需要回复的评论
        reply_comment_text: 楼中楼场景下被回复的原始评论（可选）
        max_retries: 最大重试次数

    返回：回复文本，失败返回None
    """
```

**消息构建**：
```
System: weibo_reply prompt
User:
  我的微博原文：{weibo_text}
  [我之前的评论：{reply_comment_text}]  （楼中楼场景）
  对方评论：{comment_text}
  请回复这条评论。
```

### reply_sender.py

```python
COMMENT_REPLY_URL = "https://api.weibo.com/2/comments/reply.json"

def send_reply(weibo_mid, comment_id, reply_text, rip):
    """
    回复指定评论

    参数：
        weibo_mid: 微博ID
        comment_id: 要回复的评论ID
        reply_text: 回复内容
        rip: 用户真实IP

    返回：成功返回API响应dict，失败返回None
    """
```

### run_reply.py

```python
class ReplyBot:
    """自动回复评论机器人"""

    def init(self):
        """初始化：IP → Cookie → OAuth → Selenium浏览器"""

    def poll_and_reply(self):
        """一次轮询：Selenium抓取评论 → 过滤 → AI回复 → 发送"""

    def cleanup(self):
        """关闭Selenium浏览器"""
```

集成 `TaskScheduler`，设置 `check_daily_limit=False`（回复模式自行管理上限）。
