# V2 任务拆分

## Phase 1：好友圈微博评论

### Task 1.1 - 好友圈页面抓取
- **文件**：`src/scraper/weibo_scraper.py`, `src/scraper/parser.py`
- **内容**：
  - WeiboScraper 新增 `fetch_group_timeline(gid, scroll_times)` 方法
  - parser 新增 `parse_group_weibo_cards(html)` 函数
  - 用 Selenium 加载好友圈页面，滚动加载，解析微博卡片
- **验证**：能正确抓取并解析出微博列表（mid、text、user_id 等字段）

### Task 1.2 - 好友圈配置
- **文件**：`config/config.yaml`, `src/utils/config_loader.py`
- **内容**：
  - config.yaml 新增 `friend_group` 配置段
  - config_loader 新增对应 property

### Task 1.3 - 好友圈评论主流程
- **文件**：`main.py`
- **内容**：
  - 新增好友圈轮询任务函数
  - 复用 AI 生成 + 发布 + 记录流程
  - 集成到调度器

---

## Phase 2：超话基础设施

### Task 2.1 - 超话 API 客户端
- **文件**：`src/chaohua/__init__.py`, `src/chaohua/chaohua_client.py`
- **内容**：
  - 实现 ChaohuaClient 类
  - 从 auth_url 解析认证参数
  - 实现 `get_followed_chaohua()` 获取超话列表
  - 实现基础请求方法，处理分页和错误
- **验证**：能正确获取关注超话列表

### Task 2.2 - 超话配置
- **文件**：`config/config.yaml`, `src/utils/config_loader.py`
- **内容**：
  - config.yaml 新增 `chaohua` 配置段
  - config_loader 新增对应 property

---

## Phase 3：超话签到

### Task 3.1 - 签到功能
- **文件**：`src/chaohua/chaohua_signer.py`
- **内容**：
  - 实现 ChaohuaSigner 类
  - 遍历超话列表，跳过已签到
  - 随机延迟，逐个签到
  - 签到结果记录
- **验证**：能成功完成超话签到

### Task 3.2 - 签到记录存储
- **文件**：`src/storage/record_store.py`
- **内容**：
  - 新增 `add_sign_record(topic_id, date)`
  - 新增 `is_signed_today(topic_id)`
  - 数据持久化到 JSON

---

## Phase 4：超话发帖

### Task 4.1 - 发帖功能
- **文件**：`src/chaohua/chaohua_poster.py`
- **内容**：
  - 实现 ChaohuaPoster 类
  - 支持模板和 AI 生成内容
  - 发帖到指定超话
- **验证**：能在超话中成功发帖

---

## Phase 5：超话评论

### Task 5.1 - 超话 Feed 抓取
- **文件**：`src/chaohua/chaohua_client.py`
- **内容**：
  - 实现 `get_chaohua_feed(containerid)` 获取超话微博列表

### Task 5.2 - 超话评论流程
- **文件**：`src/chaohua/chaohua_commenter.py`
- **内容**：
  - 实现 ChaohuaCommenter 类
  - 抓取 feed → 过滤 → AI 生成 → 发布评论
  - 复用现有 ai_generator 和 publisher

---

## Phase 6：调度器和主流程整合

### Task 6.1 - 调度器扩展
- **文件**：`src/scheduler/task_scheduler.py`
- **内容**：
  - 扩展支持多任务调度
  - 支持定时执行（签到）和随机间隔（评论）

### Task 6.2 - main.py 整合
- **文件**：`main.py`
- **内容**：
  - 整合好友圈评论、超话签到、超话发帖、超话评论
  - 各功能按配置 enabled 开关独立控制
  - 统一初始化和清理流程

---

## 实现顺序

```
Phase 1 (好友圈) ──→ Phase 6 (整合)
                        ↑
Phase 2 (超话基础) → Phase 3 (签到) ─┐
                  → Phase 4 (发帖) ─┤→ Phase 6
                  → Phase 5 (评论) ─┘
```

建议先完成 Phase 1（好友圈），因为它复用现有架构较多，风险较低。
然后并行开发 Phase 2-5（超话），最后 Phase 6 整合。
