"""
获取收到的评论

通过微博API获取别人对自己微博的评论，支持增量拉取。
"""

import requests

from src.auth.oauth_manager import get_valid_token
from src.utils.logger import logger

COMMENTS_TO_ME_URL = "https://api.weibo.com/2/comments/to_me.json"


def fetch_comments_to_me(since_id=0, count=50):
    """
    获取收到的评论列表（增量拉取）。

    参数：
        since_id: 上次获取的最大评论ID，只返回比此ID大的评论
        count: 每页数量，最大200

    返回：
        评论列表 [{
            "comment_id": str,
            "comment_text": str,
            "comment_user_id": str,
            "comment_user_name": str,
            "weibo_mid": str,
            "weibo_text": str,
            "reply_comment_text": str or None,
            "reply_comment_user": str or None,
            "created_at": str,
        }, ...]
    """
    access_token = get_valid_token()
    if not access_token:
        logger.error("无法获取有效的access_token，获取评论失败")
        return []

    params = {
        "access_token": access_token,
        "count": count,
    }
    if since_id:
        params["since_id"] = since_id

    try:
        resp = requests.get(COMMENTS_TO_ME_URL, params=params, timeout=15)
        data = resp.json()

        if "error_code" in data:
            error_code = data.get("error_code")
            error_msg = data.get("error", "未知错误")
            logger.error(f"获取评论失败 - 错误码: {error_code}, 信息: {error_msg}")
            if error_code in (21327, 21332):
                logger.warning("access_token无效或已过期")
            return []

        raw_comments = data.get("comments", [])
        if not raw_comments:
            logger.info("没有新评论")
            return []

        comments = []
        for c in raw_comments:
            comment_id = str(c.get("id", ""))
            if not comment_id:
                continue

            # 提取微博信息
            status = c.get("status", {})
            weibo_mid = str(status.get("mid") or status.get("id", ""))
            weibo_text = status.get("text", "")

            # 提取评论者信息
            user = c.get("user", {})
            comment_user_id = str(user.get("id", ""))
            comment_user_name = user.get("screen_name", "")

            # 提取楼中楼被回复的评论（如果有）
            reply_comment = c.get("reply_comment")
            reply_comment_text = None
            reply_comment_user = None
            if reply_comment:
                reply_comment_text = reply_comment.get("text", "")
                reply_user = reply_comment.get("user", {})
                reply_comment_user = reply_user.get("screen_name", "")

            comments.append({
                "comment_id": comment_id,
                "comment_text": c.get("text", ""),
                "comment_user_id": comment_user_id,
                "comment_user_name": comment_user_name,
                "weibo_mid": weibo_mid,
                "weibo_text": weibo_text,
                "reply_comment_text": reply_comment_text,
                "reply_comment_user": reply_comment_user,
                "created_at": c.get("created_at", ""),
            })

        logger.info(f"获取到 {len(comments)} 条新评论")
        return comments

    except requests.Timeout:
        logger.error("获取评论超时")
        return []
    except requests.ConnectionError:
        logger.error("获取评论网络连接失败")
        return []
    except Exception as e:
        logger.error(f"获取评论异常: {e}")
        return []
