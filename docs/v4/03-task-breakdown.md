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

### 2.1 reply_fetcher.py - 获取收到的评论
- 调用 `comments/to_me.json`
- 支持 since_id 增量拉取
- 解析评论数据（含微博原文、楼中楼父评论）

### 2.2 reply_generator.py - AI生成回复
- 构建回复场景的 prompt（微博原文 + 评论 + 父评论）
- 复用 LLM 调用和验证逻辑
- 支持去重

### 2.3 reply_sender.py - 发送回复
- 调用 `comments/reply.json`
- 错误处理（频率限制、内容不合规等）

**依赖**：Phase 1

## Phase 3：入口与调度

### 3.1 run_reply.py - 回复模式入口
- ReplyBot 类：init() + poll_and_reply()
- 集成 TaskScheduler 定时轮询
- 过滤逻辑：跳过自己、已回复、超限
- 信号处理与清理

**依赖**：Phase 1 + Phase 2

## Phase 4：验证

### 4.1 语法检查
- `python -m py_compile` 检查所有新文件
- `python -c "import src.reply.reply_fetcher"` 等

### 4.2 集成验证
- 运行入口文件检查初始化流程
- 检查配置加载是否正确

**依赖**：Phase 3
