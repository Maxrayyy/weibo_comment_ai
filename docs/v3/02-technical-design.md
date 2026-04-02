# V3 技术方案：表情支持 + 图片识别

## 一、表情支持

### 1.1 表情列表获取与缓存

**API接口：** `GET https://api.weibo.com/2/emotions.json`
- 参数：`access_token`, `type=face`, `language=cnname`
- 返回：`[{"phrase": "[哈哈]", "icon": "https://...png", "type": "face"}, ...]`

**缓存策略：**
- 新建 `src/emotion/emotion_manager.py`
- 首次调用时请求API，缓存到 `data/emotions_cache.json`
- 缓存有效期7天，过期自动刷新
- 提取所有 `phrase` 字段，形成可用表情名列表

### 1.2 Prompt注入表情列表

在 `ai_generator.py` 的 `_build_messages()` 中：
- 从emotion_manager获取常用表情列表（取热门的30-40个）
- 在user_prompt末尾追加可用表情提示，例如：
  ```
  你可以在评论中自然地使用微博表情，格式为[表情名]，可选表情：[哈哈][泪][心][赞]...
  不是每条都要用，觉得合适再用，最多用1-2个。
  ```

### 1.3 评论验证调整

`_validate_comment()` 中：
- 表情 `[xxx]` 不应被误判为异常内容
- 长度计算保持现有逻辑（`[哈哈]` 作为4字符计算，不影响140字限制）

## 二、图片识别

### 2.1 图片URL提取

**统一weibo数据结构扩展：**
在所有解析器中为weibo dict新增 `pic_url` 字段（第一张图片的中等尺寸URL）。

#### API模式 (`api_fetcher.py` 的 `_parse_status`)
微博API返回的status对象包含：
- `thumbnail_pic`: 缩略图URL
- `bmiddle_pic`: 中等尺寸URL
- `original_pic`: 原图URL
- `pic_ids`: 图片ID数组

提取逻辑：
```python
pic_url = status.get("bmiddle_pic", "") or ""
```

#### 好友圈Selenium模式 (`parser.py` 的 `_extract_weibo_from_article`)
好友圈页面图片在article内的 `<img>` 元素中，src指向 `sinaimg.cn`。
提取逻辑：
- 查找article内的 `img[src*="sinaimg.cn"]`
- 取第一个匹配的img的src
- 将URL中的尺寸段替换为 `mw690`（中等偏大，适合模型识别）

#### 超话Selenium模式 (`chaohua_client.py` 的 `_parse_topic_feed`)
超话页面图片在 `div.WB_media_wrap` 或 `img` 中。
提取逻辑类似好友圈模式。

### 2.2 多模态评论生成

**修改 `ai_generator.py`：**

`generate_comment` 函数签名扩展：
```python
def generate_comment(weibo_text, pic_url=None, prompt_name=None, max_retries=3)
```

`_build_messages` 函数签名扩展：
```python
def _build_messages(weibo_text, pic_url=None)
```

当 `pic_url` 存在时，user message使用多模态格式：
```python
{
    "role": "user",
    "content": [
        {"type": "text", "text": "微博内容：\n{weibo_text}\n\n请直接给出评论..."},
        {"type": "image_url", "image_url": {"url": pic_url}}
    ]
}
```

### 2.3 Prompt调整

在system_prompt末尾追加图片相关指引（仅在有图时）：
```
如果微博配了图片，可以自然地评论图片中的内容（表情、场景、食物等），
不要说"从图片中可以看到"这种分析式的话，就像朋友发了张图你随口接一句。
```

### 2.4 模型兼容性

当前使用 `qwen3.5-flash`，通义千问系列支持多模态输入。
OpenAI SDK兼容接口天然支持 `image_url` 类型的content。
如果模型不支持图片，回退到纯文本生成（捕获异常即可）。

## 三、文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/emotion/emotion_manager.py` | 新增 | 表情列表获取与缓存 |
| `src/comment/ai_generator.py` | 修改 | 注入表情、支持图片多模态 |
| `src/scraper/api_fetcher.py` | 修改 | `_parse_status` 提取 `pic_url` |
| `src/scraper/parser.py` | 修改 | 两个解析函数提取图片URL |
| `src/chaohua/chaohua_client.py` | 修改 | `_parse_topic_feed` 提取图片URL |
| `config/prompts.yaml` | 修改 | 追加图片评论指引 |
| `src/emotion/__init__.py` | 新增 | 模块初始化 |
