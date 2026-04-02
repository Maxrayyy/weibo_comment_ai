# V4 任务拆分：自动回复评论

## Phase 1：基础设施（配置 + 存储）

### 1.1 config.yaml 新增 reply 配置段
- 新增 `reply` 配置块（enabled, daily_limit, poll, delay, prompt）

### 1.2 config_loader.py 新增属性
- 新增 reply 相关配置属性（reply_enabled, reply_daily_limit 等）

### 1.3 record_store.py 新增回复记录方法
- `is_replied(comment_id)`
- `add_reply_record(...)`
- `get_reply_today_count()`
- `get_reply_since_id()` / `set_reply_since_id()`

### 1.4 prompts.yaml 新增 weibo_reply 模板
- 博主回复评论的专用 prompt

**依赖**：无

## Phase 2：核心模块

### 2.1 parser.py - 评论收件箱HTML解析器
- 新增 `parse_comment_inbox(html)` 函数
- 解析 `div.wbpro-scroller-item` 卡片
- 提取评论ID（URL中的cid）、评论内容、评论者信息
- 提取微博原文（引用区域）
- 支持楼中楼场景（识别"回复@xxx:"前缀，提取被回复评论）

### 2.2 reply_fetcher.py - Selenium抓取评论收件箱
- 访问 `https://www.weibo.com/comment/inbox`
- 等待页面加载 + 滚动加载更多
- 调用 `parse_comment_inbox` 解析HTML
- > 注：最初设计使用 `comments/to_me.json` API，因权限不足（error 10014）改为 Selenium

### 2.3 reply_generator.py - AI生成回复
- 构建回复场景的 prompt（微博原文 + 评论 + 父评论）
- 复用 LLM 调用和验证逻辑
- 支持去重

### 2.4 reply_sender.py - 发送回复
- 调用 `comments/reply.json` API
- 错误处理（频率限制、内容不合规等）

**依赖**：Phase 1

## Phase 3：入口与调度

### 3.1 run_reply.py - 回复模式入口
- ReplyBot 类：init() + poll_and_reply() + cleanup()
- init 中启动 WeiboScraper（Selenium浏览器）
- 集成 TaskScheduler 定时轮询（check_daily_limit=False）
- 过滤逻辑：跳过自己、已回复、空评论、超限
- cleanup 中关闭 Selenium 浏览器
- 信号处理与清理

**依赖**：Phase 1 + Phase 2

## Phase 4：验证

### 4.1 语法检查
- `python -m py_compile` 检查所有新文件

### 4.2 集成验证
- 运行 `test/debug_v4_reply.py` 验证完整流程
- 测试项：配置加载、Selenium抓取评论、AI回复生成、记录存储

**依赖**：Phase 3
