"""
通过微博官方API抓取好友圈微博

策略：用followers接口获取粉丝列表，从home_timeline中过滤出粉丝（互关好友）的微博。
"""

import requests

from src.auth.oauth_manager import get_valid_token
from src.utils.logger import logger

# 微博API端点
HOME_TIMELINE_URL = "https://api.weibo.com/2/statuses/home_timeline.json"
FOLLOWERS_URL = "https://api.weibo.com/2/friendships/followers.json"


def fetch_friends_weibos(count=20, page=1):
    """
    通过API获取首页时间线的微博。
    返回微博列表。
    """
    access_token = get_valid_token()
    if not access_token:
        logger.error("无法获取access_token，抓取失败")
        return []

    params = {
        "access_token": access_token,
        "count": count,
        "page": page,
    }

    try:
        resp = requests.get(HOME_TIMELINE_URL, params=params, timeout=15)
        data = resp.json()

        if "error_code" in data:
            logger.error(f"API错误 - 错误码: {data.get('error_code')}, 信息: {data.get('error')}")
            return []

        statuses = data.get("statuses", [])
        weibos = []
        for s in statuses:
            weibo = _parse_status(s)
            if weibo:
                weibos.append(weibo)

        logger.info(f"API抓取到 {len(weibos)} 条时间线微博")
        for w in weibos:
            logger.info(f"  [@{w['user_name']}] (UID:{w['user_id']}) {w['text'][:100]}")
        return weibos

    except Exception as e:
        logger.error(f"API抓取好友微博失败: {e}")
        return []


def fetch_followers(uid):
    """
    通过API获取粉丝列表。
    粉丝中同时也是你关注的人 = 互相关注（好友圈）。
    返回 [{"uid": "...", "name": "..."}, ...]
    """
    access_token = get_valid_token()
    if not access_token:
        logger.error("无法获取access_token")
        return []

    all_followers = []
    cursor = 0

    while True:
        params = {
            "access_token": access_token,
            "uid": uid,
            "count": 200,
            "cursor": cursor,
        }

        try:
            resp = requests.get(FOLLOWERS_URL, params=params, timeout=15)
            data = resp.json()

            if "error_code" in data:
                logger.error(f"API错误 - 错误码: {data.get('error_code')}, 信息: {data.get('error')}")
                break

            users = data.get("users", [])
            for u in users:
                all_followers.append({
                    "uid": str(u["id"]),
                    "name": u.get("screen_name", u.get("name", "未知")),
                })

            next_cursor = data.get("next_cursor", 0)
            if next_cursor == 0 or not users:
                break
            cursor = next_cursor

        except Exception as e:
            logger.error(f"API抓取粉丝列表失败: {e}")
            break

    logger.info(f"API获取到 {len(all_followers)} 个粉丝")
    for f in all_followers:
        logger.info(f"  粉丝: {f['name']} (UID:{f['uid']})")
    return all_followers


def _parse_status(status):
    """将API返回的微博status转为统一格式"""
    user = status.get("user", {})
    text = status.get("text", "").strip()
    if not text:
        return None

    return {
        "mid": str(status.get("mid", status.get("id", ""))),
        "user_id": str(user.get("id", "")),
        "user_name": user.get("screen_name", user.get("name", "")),
        "text": text,
        "is_repost": status.get("retweeted_status") is not None,
        "created_at": status.get("created_at", ""),
    }
