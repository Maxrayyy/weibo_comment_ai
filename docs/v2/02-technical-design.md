# V2 技术方案

## 一、架构概览

```
weibo_comment_ai/
├── main.py                          # 入口，整合所有功能
├── config/
│   ├── config.yaml                  # 新增好友圈和超话配置段
│   └── prompts.yaml                 # 复用
├── src/
│   ├── auth/
│   │   ├── login_manager.py         # 复用（PC Cookie）
│   │   └── oauth_manager.py         # 复用（API Token）
│   ├── scraper/
│   │   ├── weibo_scraper.py         # 复用 + 新增好友圈抓取方法
│   │   ├── api_fetcher.py           # 复用
│   │   └── parser.py                # 新增好友圈页面解析
│   ├── chaohua/                     # 【新模块】超话功能
│   │   ├── __init__.py
│   │   ├── chaohua_client.py        # 超话API客户端（签到/列表/发帖）
│   │   ├── chaohua_signer.py        # 签到业务逻辑
│   │   ├── chaohua_poster.py        # 发帖业务逻辑
│   │   └── chaohua_commenter.py     # 超话评论业务逻辑
│   ├── comment/
│   │   ├── ai_generator.py          # 复用
│   │   └── publisher.py             # 复用
│   ├── scheduler/
│   │   └── task_scheduler.py        # 扩展，支持多任务调度
│   └── storage/
│       └── record_store.py          # 扩展，新增签到/发帖记录
```

---

## 二、好友圈微博评论

### 2.1 技术方案

好友圈页面 `https://www.weibo.com/mygroups?gid=<gid>` 是 PC 端 SPA 页面，微博数据通过 Ajax 动态加载，无公开 REST API。

**方案：Selenium 抓取**

利用现有的 `WeiboScraper`（headless Chrome + Cookie），新增好友圈页面的抓取方法。

### 2.2 实现细节

#### WeiboScraper 新增方法

```python
def fetch_group_timeline(self, gid: str, scroll_times: int = 3) -> list[dict]:
    """抓取好友圈分组的微博feed"""
    url = f"https://www.weibo.com/mygroups?gid={gid}"
    self._safe_get(url)
    # 等待SPA渲染
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[action-type='feed_list_item']"))
    )
    # 滚动加载更多
    for _ in range(scroll_times):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(random.uniform(1.5, 3.0))
    # 解析微博卡片
    return parse_group_weibo_cards(driver.page_source)
```

#### Parser 新增解析函数

好友圈页面的微博卡片结构与首页类似，但 DOM 选择器可能不同。需要在实际抓取时确认选择器，核心提取字段：

| 字段 | 说明 |
|------|------|
| mid | 微博ID |
| user_id | 发布者UID |
| user_name | 发布者昵称 |
| text | 微博正文 |
| is_repost | 是否转发 |
| created_at | 发布时间 |

### 2.3 配置

```yaml
# config.yaml 新增
friend_group:
  enabled: true
  gid: "100097764254452"        # 好友圈分组ID
  poll_min: 60                  # 轮询间隔（秒）
  poll_max: 120
  scroll_times: 3               # 页面滚动次数
```

### 2.4 流程

```
定时触发
  → WeiboScraper.fetch_group_timeline(gid)
  → 过滤已评论 (record_store)
  → 过滤转发 (if skip_repost)
  → AI生成评论 (ai_generator)
  → 发布评论 (publisher, 需要 OAuth access_token)
  → 记录 (record_store)
```

---

## 三、超话功能

### 3.1 API 分析

超话功能使用微博**移动端内部 API**（`api.weibo.cn`），非公开 API，认证参数需通过手机抓包获取。

#### 关键 API 端点

| 功能 | URL | 方法 | 说明 |
|------|-----|------|------|
| 超话列表 | `https://api.weibo.cn/2/cardlist` | GET | containerid=100803_-_followsuper |
| 超话签到 | `https://api.weibo.cn/2/page/button` | GET/POST | 签到按钮action |
| 超话Feed | `https://api.weibo.cn/2/cardlist` | GET | containerid=超话containerid |
| 发微博 | `https://api.weibo.cn/2/statuses/send` | POST | 带超话topic参数 |

#### 认证参数

通过手机微博 App 抓包获取，关键参数：

```
gsid=xxx           # 会话标识（核心认证参数）
s=xxx              # 签名
from=xxx           # 来源标识
c=xxx              # 客户端标识
aid=xxx            # App ID
```

这些参数拼接在 URL query string 中，类似于：
```
https://api.weibo.cn/2/cardlist?gsid=_2A25xxx&s=xxx&from=10DC395010&c=android&containerid=100803_-_followsuper
```

#### 请求头

```python
HEADERS = {
    "User-Agent": "Weibo/81434 (iPhone; iOS 17.0; Scale/3.00)",
    "Host": "api.weibo.cn",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}
```

### 3.2 超话签到实现

#### ChaohuaClient（API客户端）

```python
class ChaohuaClient:
    """微博超话API客户端"""

    CARDLIST_URL = "https://api.weibo.cn/2/cardlist"
    SIGN_URL = "https://api.weibo.cn/2/page/button"
    STATUS_URL = "https://api.weibo.cn/2/statuses/send"

    def __init__(self, auth_params: dict):
        """auth_params: 从抓包URL中提取的认证参数"""
        self.auth_params = auth_params
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def get_followed_chaohua(self, since_id=None) -> list[dict]:
        """获取关注的超话列表（支持分页）"""

    def sign_in(self, chaohua_id: str) -> bool:
        """对单个超话签到"""

    def get_chaohua_feed(self, containerid: str, since_id=None) -> list[dict]:
        """获取超话内微博feed"""

    def post_to_chaohua(self, topic_id: str, content: str) -> bool:
        """在超话中发帖"""
```

#### ChaohuaSigner（签到业务）

```python
class ChaohuaSigner:
    def sign_all(self):
        """遍历关注超话，逐个签到"""
        chaohua_list = self.client.get_followed_chaohua()
        for ch in chaohua_list:
            if not ch.get("is_signed"):
                success = self.client.sign_in(ch["id"])
                # 随机延迟 5-10秒
                time.sleep(random.uniform(5, 10))
```

### 3.3 超话发帖实现

#### ChaohuaPoster

```python
class ChaohuaPoster:
    def post(self, topic_id: str, content: str = None):
        """在超话中发帖"""
        if not content:
            content = self._generate_content(topic_id)
        return self.client.post_to_chaohua(topic_id, content)

    def _generate_content(self, topic_id: str) -> str:
        """AI生成发帖内容或使用模板"""
```

### 3.4 超话评论实现

#### ChaohuaCommenter

```python
class ChaohuaCommenter:
    def comment_on_feed(self, topic_containerid: str):
        """抓取超话feed并评论"""
        feed = self.client.get_chaohua_feed(topic_containerid)
        for weibo in feed:
            if record_store.is_commented(weibo["mid"]):
                continue
            comment = generate_comment(weibo["text"])
            publish_comment(weibo["mid"], comment, rip)
            record_store.add_record(weibo["mid"], comment)
```

### 3.5 配置

```yaml
# config.yaml 新增
chaohua:
  enabled: true
  # 认证参数（从抓包URL中提取，定期更新）
  auth_url: "${WEIBO_CHAOHUA_AUTH_URL}"

  # 签到配置
  sign:
    enabled: true
    schedule: "08:00"             # 每日签到时间
    delay_min: 5                  # 签到间隔最小秒数
    delay_max: 10                 # 签到间隔最大秒数

  # 发帖配置
  post:
    enabled: false                # 默认关闭
    target_topics: []             # 目标超话containerid列表
    daily_limit: 5
    templates:                    # 发帖模板
      - "打卡"
      - "签到"

  # 评论配置
  comment:
    enabled: true
    target_topics: []             # 目标超话containerid列表
    daily_limit: 20
    poll_min: 120
    poll_max: 300
```

### 3.6 认证参数获取流程

由于超话 API 使用移动端内部接口，认证参数需要用户手动抓包获取：

1. 手机安装抓包工具（Charles / HttpCanary / Stream 等）
2. 打开微博 App，进入"超话"页面
3. 在抓包工具中搜索 `api.weibo.cn/2/cardlist`
4. 复制完整 URL（包含 gsid、s、from 等参数）
5. 将完整 URL 设置到环境变量 `WEIBO_CHAOHUA_AUTH_URL`

**注意**：认证参数会过期，需要定期更新。程序检测到认证失败时会打印提示。

---

## 四、调度器扩展

现有 `TaskScheduler` 只支持单任务。需要扩展为支持多任务并行调度：

```python
class MultiTaskScheduler:
    """多任务调度器"""

    def add_task(self, name: str, func: callable, interval_range: tuple, schedule_time: str = None):
        """
        添加调度任务
        - interval_range: (min_seconds, max_seconds) 随机间隔轮询
        - schedule_time: "HH:MM" 每日定时执行（用于签到）
        """

    def start(self):
        """启动所有已注册的任务"""

    def stop(self):
        """停止所有任务"""
```

调度策略：
- **好友圈评论**：随机间隔轮询（同现有首页评论）
- **超话签到**：每日定时执行一次
- **超话发帖**：随机间隔或定时
- **超话评论**：随机间隔轮询

---

## 五、存储扩展

`record_store.py` 扩展，新增记录类型：

```json
{
  "commented": { "mid": { ... } },
  "daily_counts": { "2026-04-01": 5 },
  "chaohua_signed": { "2026-04-01": ["topic1", "topic2"] },
  "chaohua_posted": { "mid": { ... } },
  "chaohua_commented": { "mid": { ... } }
}
```

---

## 六、风险和注意事项

| 风险 | 应对 |
|------|------|
| 好友圈页面 DOM 结构变化 | 选择器集中配置，便于快速更新 |
| 超话 API 参数过期 | 检测 401/403 响应，提示用户更新 |
| 超话 API 接口变更 | 参考文档中记录的接口为2025年版本，实际实现时需验证 |
| 频率限制/封号 | 严格随机延迟 + 每日限额 + 工作时间窗口 |
| Selenium 资源占用 | 好友圈抓取完毕后及时关闭 browser session |
