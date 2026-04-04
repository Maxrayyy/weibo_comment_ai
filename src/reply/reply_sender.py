"""
回复评论发送模块

通过Selenium浏览器执行AJAX请求回复评论，使用Cookie认证，不消耗OAuth API配额。
"""

import json

from src.comment.publisher import RateLimitError
from src.utils.logger import logger

COMMENT_REPLY_URL = "https://www.weibo.com/ajax/comments/reply"


def send_reply(driver, weibo_mid, comment_id, reply_text, root_comment_id=None, reply_user_name=None):
    """
    通过微博网页AJAX接口回复指定评论。

    参数：
        driver: Selenium WebDriver 实例（需已登录微博）
        weibo_mid: 微博ID
        comment_id: 要回复的评论ID
        reply_text: 回复内容
        root_comment_id: 楼中楼场景下的根评论ID（可选，不传则视为直接回复根评论）
        reply_user_name: 楼中楼场景下被回复者昵称（可选，用于添加@前缀）

    返回：
        成功返回API响应dict，失败返回None
    """
    try:
        # 楼中楼回复：cid=根评论ID, reply_id=被回复的具体评论ID，内容前加"回复@用户名:"
        if root_comment_id:
            cid = str(root_comment_id)
            reply_id = str(comment_id)
            if reply_user_name:
                reply_text = f"回复@{reply_user_name}:{reply_text}"
        else:
            cid = str(comment_id)
            reply_id = str(comment_id)

        safe_comment = _js_escape(reply_text)
        safe_mid = _js_escape(str(weibo_mid))
        safe_cid = _js_escape(cid)
        safe_reply_id = _js_escape(reply_id)

        result = driver.execute_script(f"""
            try {{
                var xhr = new XMLHttpRequest();
                xhr.open('POST', '{COMMENT_REPLY_URL}', false);
                xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
                xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
                var xsrf = document.cookie.match(/XSRF-TOKEN=([^;]+)/);
                if (xsrf) {{
                    xhr.setRequestHeader('X-XSRF-TOKEN', decodeURIComponent(xsrf[1]));
                }}
                var params = 'id={safe_mid}&cid={safe_cid}&reply_id={safe_reply_id}&comment=' + encodeURIComponent('{safe_comment}');
                xhr.send(params);
                return JSON.stringify({{status: xhr.status, body: xhr.responseText}});
            }} catch(e) {{
                return JSON.stringify({{status: 0, body: e.message}});
            }}
        """)

        if not result:
            logger.error("回复发送失败：浏览器未返回结果")
            return None

        resp = json.loads(result)
        status = resp.get("status", 0)
        body_text = resp.get("body", "")

        if status == 200:
            try:
                body = json.loads(body_text)
            except json.JSONDecodeError:
                logger.error(f"回复响应解析失败: {body_text[:200]}")
                return None

            if "id" in body:
                logger.info(f"回复发送成功！评论ID: {comment_id}, 回复ID: {body['id']}")
                return body
            elif body.get("ok") == 1:
                logger.info(f"回复发送成功！评论ID: {comment_id}, msg: {body.get('msg', '')}")
                return body
            else:
                error_code = body.get("error_code", body.get("errno", "未知"))
                error_msg = body.get("error", body.get("msg", "未知错误"))
                logger.error(f"回复发送失败 - 错误码: {error_code}, 信息: {error_msg}")
                return None
        elif status == 403:
            logger.warning("回复发送被拒绝(403)，可能触发频率限制")
            raise RateLimitError("回复频率限制: HTTP 403")
        elif status == 414:
            logger.warning("回复发送触发频率限制(414)")
            raise RateLimitError("回复频率限制: HTTP 414")
        else:
            logger.error(f"回复发送HTTP错误: {status}, 响应: {body_text[:200]}")
            return None

    except RateLimitError:
        raise
    except Exception as e:
        logger.error(f"回复发送异常: {e}")
        return None


def _js_escape(text):
    """转义文本用于嵌入JS字符串（单引号包裹）"""
    return (text
            .replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace("\n", "\\n")
            .replace("\r", "\\r"))
