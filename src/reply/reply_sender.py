"""
回复评论发送模块

通过微博API回复指定评论。
"""

import requests

from src.auth.oauth_manager import get_valid_token
from src.utils.logger import logger

COMMENT_REPLY_URL = "https://api.weibo.com/2/comments/reply.json"


def send_reply(weibo_mid, comment_id, reply_text, rip):
    """
    回复指定评论。

    参数：
        weibo_mid: 微博ID
        comment_id: 要回复的评论ID
        reply_text: 回复内容
        rip: 用户真实IP

    返回：
        成功返回API响应dict，失败返回None
    """
    access_token = get_valid_token()
    if not access_token:
        logger.error("无法获取有效的access_token，回复发送失败")
        return None

    data = {
        "access_token": access_token,
        "id": weibo_mid,
        "cid": comment_id,
        "comment": reply_text,
        "without_mention": 0,
        "comment_ori": 0,
        "rip": rip,
    }

    try:
        resp = requests.post(COMMENT_REPLY_URL, data=data, timeout=15)
        result = resp.json()

        if "id" in result:
            logger.info(f"回复发送成功！评论ID: {comment_id}, 回复ID: {result['id']}")
            return result
        else:
            error_code = result.get("error_code", "未知")
            error_msg = result.get("error", "未知错误")
            logger.error(f"回复发送失败 - 错误码: {error_code}, 信息: {error_msg}")

            if error_code == 10023:
                logger.warning("触发频率限制，请稍后再试")
            elif error_code == 10014:
                logger.warning("回复内容不合规")
            elif error_code in (21327, 21332):
                logger.warning("access_token无效或已过期")

            return None

    except requests.Timeout:
        logger.error(f"回复发送超时，评论ID: {comment_id}")
        return None
    except requests.ConnectionError:
        logger.error(f"回复发送网络连接失败，评论ID: {comment_id}")
        return None
    except Exception as e:
        logger.error(f"回复发送异常: {e}")
        return None
