# V3 任务拆分

## Phase 1：表情支持

### Task 1.1：表情管理模块
- 新建 `src/emotion/__init__.py` 和 `src/emotion/emotion_manager.py`
- 实现 `get_emotion_list()` 获取并缓存表情
- 缓存到 `data/emotions_cache.json`，7天有效期

### Task 1.2：AI生成器注入表情
- 修改 `ai_generator.py` 的 `_build_messages()`
- 在user_prompt中追加可用表情列表提示

## Phase 2：图片提取

### Task 2.1：API模式图片提取
- 修改 `api_fetcher.py` 的 `_parse_status()`，提取 `pic_url`

### Task 2.2：好友圈Selenium模式图片提取
- 修改 `parser.py` 的 `_extract_weibo_from_article()`，提取图片URL

### Task 2.3：超话Selenium模式图片提取
- 修改 `chaohua_client.py` 的 `_parse_topic_feed()`，提取图片URL

## Phase 3：多模态评论生成

### Task 3.1：AI生成器支持图片输入
- 修改 `generate_comment()` 和 `_build_messages()` 支持 `pic_url` 参数
- 有图时使用多模态message格式
- 无图时保持原逻辑不变

### Task 3.2：Prompt调整
- `prompts.yaml` 中追加图片评论指引

### Task 3.3：调用方传递图片URL
- 修改 `main.py`、`run_friend_group.py`、`chaohua_commenter.py` 中调用 `generate_comment` 的地方，传入 `pic_url`

## Phase 4：验证

### Task 4.1：编译检查 + 调试脚本测试
- `python -m py_compile` 检查所有修改的文件
- 运行debug脚本验证表情注入和图片提取
