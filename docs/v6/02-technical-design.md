# V6 技术方案：AJAX 评论/回复

## 接口分析

### 发评论
- URL: `POST https://www.weibo.com/ajax/comments/create`
- 参数: `id` (微博mid), `comment` (评论文本)
- 认证: Cookie + X-XSRF-TOKEN header

### 回复评论
- URL: `POST https://www.weibo.com/ajax/comments/reply`
- 参数: `id` (微博mid), `cid` (评论ID), `reply_id` (楼中楼回复ID, 可选), `comment` (回复文本)
- 认证: 同上

## 实现方案

参考现有 `weibo_scraper.py` 的 `_fetch_group_via_api()` 方法（XMLHttpRequest同步调用），在浏览器上下文中执行 XHR POST 请求。

### 改造方式
直接修改 `publisher.py` 和 `reply_sender.py`，函数签名改为接收 `driver` 参数替代 `rip`+`access_token`。
不再依赖 OAuth token，完全通过浏览器 Cookie 认证。

### 错误处理
- 响应中包含 `id` 字段 → 成功
- HTTP 403/频率限制 → 抛出 RateLimitError
- 其他错误 → 返回 None

## 任务拆分

1. 修改 `src/comment/publisher.py` — 改用 AJAX
2. 修改 `src/reply/reply_sender.py` — 改用 AJAX
3. 更新调用方传入 driver 参数
4. 移除不再需要的 rip 和 OAuth 依赖（在评论/回复模块中）
5. 验证
