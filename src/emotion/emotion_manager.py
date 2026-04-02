"""
微博表情管理模块

获取微博官方表情列表并缓存到本地，供AI生成评论时使用。
API: GET https://api.weibo.com/2/emotions.json
"""

import json
import os
import time

import requests

from src.auth.oauth_manager import get_valid_token
from src.utils.logger import logger

EMOTIONS_API = "https://api.weibo.com/2/emotions.json"
CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "emotions_cache.json"
)
CACHE_TTL = 7 * 24 * 3600  # 7天

# 模块级缓存，避免重复读文件
_cached_phrases = None


def _fetch_from_api():
    """从微博API获取表情列表"""
    access_token = get_valid_token()
    if not access_token:
        logger.error("无法获取access_token，表情列表获取失败")
        return []

    try:
        resp = requests.get(
            EMOTIONS_API,
            params={"access_token": access_token, "type": "face", "language": "cnname"},
            timeout=15,
        )
        data = resp.json()

        if isinstance(data, list):
            phrases = [item["phrase"] for item in data if "phrase" in item]
            logger.info(f"从API获取到 {len(phrases)} 个表情")
            return phrases

        logger.error(f"表情API返回异常: {data}")
        return []

    except Exception as e:
        logger.error(f"获取表情列表异常: {e}")
        return []


def _load_cache():
    """从本地缓存加载表情列表"""
    if not os.path.exists(CACHE_PATH):
        return None

    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)

        if time.time() - cache.get("timestamp", 0) > CACHE_TTL:
            logger.info("表情缓存已过期")
            return None

        phrases = cache.get("phrases", [])
        if phrases:
            logger.info(f"从缓存加载 {len(phrases)} 个表情")
        return phrases

    except Exception as e:
        logger.warning(f"读取表情缓存失败: {e}")
        return None


def _save_cache(phrases):
    """保存表情列表到本地缓存"""
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"timestamp": time.time(), "phrases": phrases}, f, ensure_ascii=False)
        logger.info(f"表情缓存已保存，共 {len(phrases)} 个")
    except Exception as e:
        logger.warning(f"保存表情缓存失败: {e}")


def get_emotion_list():
    """
    获取微博表情列表（优先缓存，过期则刷新）。
    返回: ["[哈哈]", "[泪]", "[心]", ...]
    """
    global _cached_phrases
    if _cached_phrases:
        return _cached_phrases

    phrases = _load_cache()
    if not phrases:
        phrases = _fetch_from_api()
        if phrases:
            _save_cache(phrases)

    _cached_phrases = phrases or []
    return _cached_phrases


def get_emotion_prompt_text(max_count=40):
    """
    获取用于注入prompt的表情提示文本。
    返回: 格式化的表情提示字符串，如果没有表情则返回空字符串。
    """
    phrases = get_emotion_list()
    if not phrases:
        return ""

    sample = phrases[:max_count]
    emotion_str = "".join(sample)
    return (
        f"\n\n你可以在评论中自然地使用微博表情，格式为[表情名]，可选表情：{emotion_str}\n"
        f"不是每条都要用，觉得合适再用，最多1-2个。"
    )
