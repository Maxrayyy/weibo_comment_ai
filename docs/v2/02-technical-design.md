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

### 3.1 技术方案

> **注**：最初设计使用微博移动端 API（`api.weibo.cn`）+ 手机抓包获取认证参数，但实际实现中改为 **PC Cookie + Selenium** 方案，无需手机抓包，与好友圈功能共用认证体系。

超话功能通过 Selenium 操作 PC 端微博页面，结合 requests 调用 PC 端可用的 API 实现。

#### 认证方式

- 复用 `login_manager.py` 的 PC Cookie（与好友圈、时间线模式共用）
- ChaohuaClient 接受 `uid`、`cookies`、`driver` 参数
- 无需手机抓包或移动端认证参数

### 3.2 超话签到实现

#### ChaohuaClient（超话客户端）

```python
class ChaohuaClient:
    """微博超话客户端（基于PC Cookie + Selenium）"""

    def __init__(self, uid, cookies, driver):
        """
        uid: 用户UID
        cookies: PC端Cookie列表
        driver: Selenium WebDriver实例
        """

    def get_followed_chaohua(self) -> list[dict]:
        """获取关注的超话列表"""

    def sign_in(self, containerid: str) -> bool:
        """对单个超话签到"""

    def get_topic_feed(self, containerid: str, scroll_times=2) -> list[dict]:
        """获取超话内微博feed"""

    def post_to_topic(self, containerid: str, content: str) -> bool:
        """在超话中发帖（通过Selenium模拟用户操作）"""
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
  # 无需移动端认证参数，使用PC Cookie

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

### 3.6 认证说明

超话功能使用 PC Cookie 认证，与好友圈、时间线模式共用 `data/cookies.json`。无需手机抓包或额外配置认证参数。

Cookie 过期时程序会自动打开浏览器窗口提示重新登录。

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
| PC Cookie 过期 | 检测登录状态，自动提示重新登录 |
| 超话页面结构变更 | Selenium选择器集中配置，便于更新 |
| 频率限制/封号 | 严格随机延迟 + 每日限额 + 工作时间窗口 |
| Selenium 资源占用 | 好友圈抓取完毕后及时关闭 browser session |
