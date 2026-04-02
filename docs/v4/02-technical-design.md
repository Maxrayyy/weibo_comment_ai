# V4 技术方案：自动回复评论

## 架构设计

### 新增模块

```
src/
├── reply/                          # 新增：回复模块
│   ├── reply_fetcher.py            # 获取收到的评论
│   ├── reply_generator.py          # AI生成回复内容
│   └── reply_sender.py             # 发送回复
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
  └─ 获取自己的UID
  ↓
TaskScheduler 定时轮询
  ↓
ReplyBot.poll_and_reply()
  ├─ 1. 获取收到的评论列表 (reply_fetcher)
  │     └─ GET comments/to_me.json
  ├─ 2. 过滤：跳过自己、已回复、非工作时段
  ├─ 3. 对每条评论：
  │     ├─ a. 收集上下文（微博原文 + 评论 + 父评论）
  │     ├─ b. AI生成回复 (reply_generator)
  │     ├─ c. 随机延迟
  │     └─ d. 发送回复 (reply_sender)
  │           └─ POST comments/reply.json
  └─ 4. 记录已回复
```

## 接口分析

### 1. 获取收到的评论

**接口**：`GET https://api.weibo.com/2/comments/to_me.json`

**参数**：
| 参数 | 类型 | 说明 |
|------|------|------|
| access_token | string | OAuth token |
| since_id | int64 | 上次获取的最大评论ID，用于增量拉取 |
| max_id | int64 | 返回小于等于此ID的评论 |
| count | int | 每页数量，默认50，最大200 |
| page | int | 页码 |
| filter_by_author | int | 0-全部，1-关注的人，2-陌生人 |

**返回数据结构**：
```json
{
  "comments": [
    {
      "id": 1234567890,
      "text": "评论内容",
      "created_at": "Mon Jan 01 12:00:00 +0800 2025",
      "user": {
        "id": 123456,
        "screen_name": "用户昵称"
      },
      "status": {
        "id": 9876543210,
        "mid": "9876543210",
        "text": "微博原文内容",
        "user": {
          "id": 654321,
          "screen_name": "博主昵称"
        }
      },
      "reply_comment": {
        "id": 1111111111,
        "text": "被回复的评论内容",
        "user": {
          "id": 222222,
          "screen_name": "被回复者"
        }
      }
    }
  ],
  "total_number": 100
}
```

**关键点**：
- `status` 字段包含被评论的微博原文
- `reply_comment` 字段包含楼中楼场景下被回复的评论（如果是直接评论微博则无此字段）
- 使用 `since_id` 实现增量拉取，避免重复处理

### 2. 回复评论

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

### 3. 获取单条微博信息（备用）

**接口**：`GET https://api.weibo.com/2/statuses/show.json`

**参数**：access_token, id（微博ID）

**用途**：当 `comments/to_me` 返回的 status 信息不完整时，补充获取微博原文。

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
- `get_reply_since_id()` / `set_reply_since_id(since_id)` - 增量拉取游标

## 模块详细设计

### reply_fetcher.py

```python
COMMENTS_TO_ME_URL = "https://api.weibo.com/2/comments/to_me.json"

def fetch_comments_to_me(since_id=0, count=50):
    """
    获取收到的评论列表（增量拉取）
    
    返回：[{
        "comment_id": str,       # 评论ID
        "comment_text": str,     # 评论内容
        "comment_user_id": str,  # 评论者UID
        "comment_user_name": str,# 评论者昵称
        "weibo_mid": str,        # 微博ID
        "weibo_text": str,       # 微博原文
        "reply_comment_text": str,  # 被回复的评论（楼中楼，可选）
        "reply_comment_user": str,  # 被回复者昵称（可选）
        "created_at": str,       # 评论时间
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
  微博原文：{weibo_text}
  [你之前的评论：{reply_comment_text}]  （楼中楼场景）
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
