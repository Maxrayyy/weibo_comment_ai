"""
微博评论发布模块

通过Selenium浏览器执行AJAX请求发布评论，使用Cookie认证，不消耗OAuth API配额。
"""

import json

from src.utils.logger import logger


COMMENT_CREATE_URL = "https://www.weibo.com/ajax/comments/create"


class RateLimitError(Exception):
    """触发API频率限制"""
    pass


def publish_comment(driver, weibo_mid, comment_text):
    """
    通过微博网页AJAX接口发布评论。

    参数：
        driver: Selenium WebDriver 实例（需已登录微博）
        weibo_mid: 微博ID
        comment_text: 评论内容

    返回：
        成功返回API响应dict，失败返回None
    raises：
        RateLimitError: 触发频率限制时抛出，由上层决定是否停止
    """
    try:
        # 对评论内容进行JS转义（防止引号和换行破坏JS字符串）
        safe_comment = _js_escape(comment_text)
        safe_mid = _js_escape(str(weibo_mid))

        result = driver.execute_script(f"""
            try {{
                var xhr = new XMLHttpRequest();
                xhr.open('POST', '{COMMENT_CREATE_URL}', false);
                xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
                xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
                xhr.setRequestHeader('client-version', '3.0.0');
                xhr.setRequestHeader('server-version', 'v2026.04.03.1');
                // 从Cookie中读取XSRF-TOKEN
                var xsrf = document.cookie.match(/XSRF-TOKEN=([^;]+)/);
                if (xsrf) {{
                    xhr.setRequestHeader('X-XSRF-TOKEN', decodeURIComponent(xsrf[1]));
                }}
                var params = 'id={safe_mid}&comment=' + encodeURIComponent('{safe_comment}');
                xhr.send(params);
                return JSON.stringify({{status: xhr.status, body: xhr.responseText}});
            }} catch(e) {{
                return JSON.stringify({{status: 0, body: e.message}});
            }}
        """)

        if not result:
            logger.error("评论发布失败：浏览器未返回结果")
            return None

        resp = json.loads(result)
        status = resp.get("status", 0)
        body_text = resp.get("body", "")

        if status == 200:
            try:
                body = json.loads(body_text)
            except json.JSONDecodeError:
                logger.error(f"评论发布响应解析失败: {body_text[:200]}")
                return None

            if "id" in body:
                logger.info(f"评论发布成功！微博ID: {weibo_mid}, 评论ID: {body['id']}")
                return body
            elif body.get("ok") == 1:
                logger.info(f"评论发布成功！微博ID: {weibo_mid}, msg: {body.get('msg', '')}")
                return body
            else:
                error_code = body.get("error_code", body.get("errno", "未知"))
                error_msg = body.get("error", body.get("msg", "未知错误"))
                logger.error(f"评论发布失败 - 错误码: {error_code}, 信息: {error_msg}")
                return None
        elif status == 403:
            logger.warning("评论发布被拒绝(403)，可能触发频率限制")
            raise RateLimitError("评论频率限制: HTTP 403")
        elif status == 414:
            logger.warning("评论发布触发频率限制(414)")
            raise RateLimitError("评论频率限制: HTTP 414")
        else:
            logger.error(f"评论发布HTTP错误: {status}, 响应: {body_text[:200]}")
            return None

    except RateLimitError:
        raise
    except Exception as e:
        logger.error(f"评论发布异常: {e}")
        return None


def _js_escape(text):
    """转义文本用于嵌入JS字符串（单引号包裹）"""
    return (text
            .replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace("\n", "\\n")
            .replace("\r", "\\r"))
