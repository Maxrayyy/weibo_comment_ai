"""
微博评论发布模块

通过微博官方API发布评论。
"""

import requests
from urllib.parse import quote

from src.auth.oauth_manager import get_valid_token
from src.utils.logger import logger

COMMENT_CREATE_URL = "https://api.weibo.com/2/comments/create.json"


def publish_comment(weibo_mid, comment_text):
    """
    通过微博API发布评论。

    参数：
        weibo_mid: 微博ID
        comment_text: 评论内容

    返回：
        成功返回API响应dict，失败返回None
    """
    access_token = get_valid_token()
    if not access_token:
        logger.error("无法获取有效的access_token，评论发布失败")
        return None

    data = {
        "access_token": access_token,
        "id": weibo_mid,
        "comment": comment_text,
    }

    try:
        resp = requests.post(COMMENT_CREATE_URL, data=data, timeout=15)
        result = resp.json()

        if "id" in result:
            logger.info(f"评论发布成功！微博ID: {weibo_mid}, 评论ID: {result['id']}")
            return result
        else:
            error_code = result.get("error_code", "未知")
            error_msg = result.get("error", "未知错误")
            logger.error(f"评论发布失败 - 错误码: {error_code}, 信息: {error_msg}")

            # 特殊错误处理
            if error_code == 10023:
                logger.warning("触发频率限制，请稍后再试")
            elif error_code == 10014:
                logger.warning("评论内容不合规")
            elif error_code in (21327, 21332):
                logger.warning("access_token无效或已过期")

            return None

    except requests.Timeout:
        logger.error(f"评论发布超时，微博ID: {weibo_mid}")
        return None
    except requests.ConnectionError:
        logger.error(f"评论发布网络连接失败，微博ID: {weibo_mid}")
        return None
    except Exception as e:
        logger.error(f"评论发布异常: {e}")
        return None
