# V6 需求：评论/回复改用网页AJAX接口

## 背景
微博OAuth API有严格的频率限制（单用户100次/天），多服务共享配额导致回复服务无法正常工作。

## 目标
将评论发布和回复发送从 OAuth API (`api.weibo.com`) 改为微博网页内部 AJAX 接口 (`www.weibo.com/ajax/`)，通过 Selenium 浏览器执行，使用 Cookie 认证，绕开 OAuth API 配额限制。

## 影响范围
- `src/comment/publisher.py` — `publish_comment()` 函数
- `src/reply/reply_sender.py` — `send_reply()` 函数
- 调用方：`run_friend_group.py`, `run_reply.py`, `src/chaohua/chaohua_commenter.py`

## 约束
- 保持 `RateLimitError` 异常机制，网页端也可能有频率限制
- 需要 Selenium driver 实例，调用方需传入
- 必须在 `www.weibo.com` 域下执行（跨域限制）
