# 微博全自动评论系统 — 实施计划

> 基于设计文档：`2026-03-31-weibo-auto-comment-design.md`

---

## 阶段一：项目基础搭建

### 任务 1.1 — 创建项目目录结构
- 创建 `config/`、`src/`（含子模块）、`logs/` 目录
- 创建所有 `__init__.py` 文件
- **验证**：`tree` 命令输出与设计文档中的文件结构一致

### 任务 1.2 — 创建配置文件
- 创建 `config/config.yaml`（主配置，敏感字段用占位符）
- 创建 `config/prompts.yaml`（三种评论风格模板）
- **验证**：Python 能正确加载两个 YAML 文件

### 任务 1.3 — 更新 requirements.txt 并安装依赖
- 更新 `requirements.txt`：requests, selenium, webdriver-manager, beautifulsoup4, pyyaml, apscheduler, openai
- **验证**：`pip install -r requirements.txt` 成功

### 任务 1.4 — 实现日志工具 (src/utils/logger.py)
- 配置 logging 模块，同时输出到控制台和 `logs/app.log`
- 支持日志级别配置
- **验证**：导入 logger，调用 `logger.info("test")` 能同时在控制台和文件中看到输出

### 任务 1.5 — 实现配置管理模块
- 在 `src/utils/` 中添加 `config_loader.py`
- 加载 `config.yaml` 和 `prompts.yaml`，提供全局配置访问
- **验证**：`from src.utils.config_loader import config` 能正确读取所有配置项

---

## 阶段二：登录与认证模块

### 任务 2.1 — 实现 Cookie 登录管理 (src/auth/login_manager.py)
- Selenium 打开微博登录页 `https://passport.weibo.com/sso/signin`
- 控制台提示用户手动完成登录
- 循环检测登录成功（检查 URL 或页面元素变化）
- 登录成功后提取 Cookie，保存到 `data/cookies.json`
- **验证**：运行后手动登录，Cookie 文件成功生成

### 任务 2.2 — 实现 Cookie 加载与验证
- 从 `data/cookies.json` 加载 Cookie
- 用 Selenium 加载 Cookie 后访问微博，验证是否仍登录状态
- Cookie 无效时返回失败标记，触发重新登录
- **验证**：加载已保存的 Cookie，能正常访问微博首页

### 任务 2.3 — 实现 OAuth2 认证管理 (src/auth/oauth_manager.py)
- 实现授权码获取流程：用 Selenium 打开授权页面，用户授权后从回调 URL 提取 code
- 实现 access_token 获取：用 code 换取 token
- 实现 token 有效性检查（调用 `account/get_uid` 接口）
- Token 和过期时间持久化到 `data/oauth_token.json`
- **验证**：运行后能成功获取 access_token 并获取到用户 UID

---

## 阶段三：微博抓取模块

### 任务 3.1 — 实现微博页面抓取器 (src/scraper/weibo_scraper.py)
- 使用已保存的 Cookie 初始化 Selenium 浏览器
- 实现访问用户主页并获取微博列表的方法
- 实现访问首页时间线并获取微博列表的方法
- 处理页面加载等待和滚动加载
- **验证**：能成功抓取到指定用户主页上的微博 HTML

### 任务 3.2 — 实现微博内容解析器 (src/scraper/parser.py)
- 用 BeautifulSoup 解析微博页面 HTML
- 提取微博 ID (mid)、发布者 UID 和昵称、微博正文、发布时间、是否转发
- 返回结构化的微博对象列表
- **验证**：传入抓取的 HTML，能正确解析出至少 5 条微博信息

### 任务 3.3 — 实现好友列表抓取
- 抓取当前用户的关注列表页面
- 解析出所有关注用户的 UID 和昵称
- 处理分页（关注列表可能有多页）
- **验证**：能获取到完整的关注列表

### 任务 3.4 — 实现新微博检测逻辑
- 加载已评论记录（`data/commented_records.json`）
- 将抓取到的微博与已评论记录对比
- 根据配置的白名单/黑名单过滤用户
- 根据配置决定是否跳过转发微博
- 返回待评论的新微博列表
- **验证**：首次运行返回所有微博，第二次运行（标记部分为已评论后）返回剩余微博

---

## 阶段四：AI 评论生成模块

### 任务 4.1 — 实现 Qwen API 评论生成器 (src/comment/ai_generator.py)
- 使用 OpenAI SDK（兼容 Qwen API）
- 根据配置加载对应的评论风格 system prompt
- 传入微博正文内容，生成评论
- 评论合规检查：长度≤140字、不含敏感词
- 生成失败时支持重试（最多3次）
- **验证**：传入一段微博文本，能返回一条合理的评论

### 任务 4.2 — 实现评论多样性保障
- 记录最近 20 条已生成的评论内容
- 新生成的评论与历史评论对比，重复度过高时重新生成
- 在 prompt 中加入随机元素（如"这次用更轻松的语气"等）
- **验证**：对同一条微博生成 5 次评论，内容各不相同

---

## 阶段五：评论发布模块

### 任务 5.1 — 实现微博 API 评论发布 (src/comment/publisher.py)
- 调用 `comments/create` 接口发布评论
- 发布前检查 access_token 是否有效，无效则自动刷新
- 处理 API 返回的错误码（频率限制、权限不足等）
- 发布成功后记录到已评论记录
- **验证**：传入一条微博 ID 和评论内容，能成功发布评论

### 任务 5.2 — 实现已评论记录存储 (src/storage/record_store.py)
- 保存已评论微博 ID、评论时间、评论内容到 `data/commented_records.json`
- 支持查询某条微博是否已评论
- 记录每日评论计数
- **验证**：写入记录后能正确查询到

---

## 阶段六：调度器与主程序

### 任务 6.1 — 实现随机间隔调度器 (src/scheduler/task_scheduler.py)
- 基于 APScheduler 实现随机间隔的任务调度
- 每次任务执行后随机计算下一次执行时间（poll_min ~ poll_max）
- 支持工作时段控制（非工作时段自动暂停）
- 支持每日评论数上限检查
- **验证**：启动调度器，观察任务以随机间隔执行

### 任务 6.2 — 实现主程序入口 (main.py)
- 整合所有模块的完整工作流：
  1. 加载配置
  2. 初始化日志
  3. 登录/Cookie 验证
  4. OAuth 认证
  5. 启动调度器
  6. 调度器循环：抓取新微博 → AI 生成评论 → 随机延迟 → API 发布评论
- 支持优雅退出（Ctrl+C）
- **验证**：运行 `python main.py`，程序完整执行一个周期

---

## 阶段七：集成测试与优化

### 任务 7.1 — 端到端集成测试
- 配置白名单中的 1-2 个好友
- 运行完整流程：登录 → 抓取 → 生成评论 → 发布
- 确认评论成功出现在微博页面上
- **验证**：至少成功自动评论 3 条微博

### 任务 7.2 — 异常处理完善
- 网络超时重试
- Selenium 页面加载失败恢复
- API 调用失败的降级处理
- Cookie/Token 过期的自动检测和提醒
- **验证**：模拟各种异常场景，程序不会崩溃

### 任务 7.3 — 更新 README.md
- 项目说明、功能介绍
- 安装和配置步骤
- 使用方法
- 注意事项

---

## 实施顺序总结

| 阶段 | 任务数 | 依赖 | 说明 |
|------|--------|------|------|
| 一：基础搭建 | 5个 | 无 | 项目骨架、配置、日志 |
| 二：登录认证 | 3个 | 阶段一 | Cookie + OAuth |
| 三：微博抓取 | 4个 | 阶段二 | Selenium抓取 + 解析 |
| 四：AI评论 | 2个 | 阶段一 | Qwen API调用 |
| 五：评论发布 | 2个 | 阶段二、四 | API发布 + 记录 |
| 六：调度主程序 | 2个 | 全部 | 整合所有模块 |
| 七：测试优化 | 3个 | 全部 | 集成测试 + 收尾 |

**总计 21 个任务，阶段四可与阶段二、三并行开发。**
