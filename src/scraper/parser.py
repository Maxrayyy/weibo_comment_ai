"""
微博页面HTML解析器

使用BeautifulSoup解析微博网页版HTML，提取微博和用户信息。
"""

import re
from bs4 import BeautifulSoup

from src.utils.logger import logger


def parse_weibo_cards(html):
    """
    从微博页面HTML中解析微博卡片信息。
    返回微博列表，每条微博包含：
    {
        "mid": 微博ID,
        "user_id": 发布者UID,
        "user_name": 发布者昵称,
        "text": 微博正文,
        "is_repost": 是否为转发,
        "created_at": 发布时间文本,
    }
    """
    soup = BeautifulSoup(html, "html.parser")
    weibos = []

    # 微博网页版的微博卡片通常包含 mid 属性或 data-mid 属性
    # 尝试多种选择器适配不同版本页面
    cards = soup.find_all(attrs={"mid": True})
    if not cards:
        cards = soup.find_all(attrs={"data-mid": True})
    if not cards:
        # 新版微博可能使用不同的结构，尝试通过class匹配
        cards = soup.find_all("div", class_=re.compile(r"card-wrap|wbpro-feed"))

    for card in cards:
        try:
            weibo = _extract_weibo_from_card(card)
            if weibo and weibo.get("mid") and weibo.get("text"):
                weibos.append(weibo)
        except Exception as e:
            logger.debug(f"解析微博卡片失败: {e}")
            continue

    return weibos


def _extract_weibo_from_card(card):
    """从单个微博卡片中提取信息"""
    weibo = {}

    # 提取微博ID
    weibo["mid"] = card.get("mid") or card.get("data-mid") or ""

    # 提取发布者信息
    user_link = card.find("a", class_=re.compile(r"name|head-info|user"))
    if user_link:
        weibo["user_name"] = user_link.get_text(strip=True)
        href = user_link.get("href", "")
        # 从href中提取UID: /u/1234567890 或 /username
        uid_match = re.search(r"/u/(\d+)", href)
        weibo["user_id"] = uid_match.group(1) if uid_match else ""
    else:
        weibo["user_name"] = ""
        weibo["user_id"] = ""

    # 提取微博正文
    text_elem = card.find("div", class_=re.compile(r"txt|text|content|detail"))
    if text_elem:
        # 移除内嵌链接文本中的无关内容
        for a in text_elem.find_all("a"):
            if "展开" in a.get_text() or "收起" in a.get_text():
                a.decompose()
        weibo["text"] = text_elem.get_text(strip=True)
    else:
        weibo["text"] = ""

    # 判断是否为转发微博
    repost_elem = card.find("div", class_=re.compile(r"repost|card-comment|forward"))
    weibo["is_repost"] = repost_elem is not None

    # 提取发布时间
    time_elem = card.find("a", class_=re.compile(r"time|from")) or card.find("span", class_=re.compile(r"time|from"))
    weibo["created_at"] = time_elem.get_text(strip=True) if time_elem else ""

    return weibo


def parse_follow_list(html):
    """
    从关注列表页面解析关注用户信息。
    返回 [{"uid": "...", "name": "..."}, ...]
    """
    soup = BeautifulSoup(html, "html.parser")
    follows = []

    # 关注列表中的用户卡片
    user_cards = soup.find_all("div", class_=re.compile(r"card|follow-item|member"))

    for card in user_cards:
        try:
            user_link = card.find("a", class_=re.compile(r"name|S_txt1|avator"))
            if not user_link:
                user_link = card.find("a", href=re.compile(r"/u/\d+"))
            if not user_link:
                continue

            name = user_link.get_text(strip=True)
            href = user_link.get("href", "")
            uid_match = re.search(r"/u/(\d+)", href)
            uid = uid_match.group(1) if uid_match else ""

            if uid and name:
                follows.append({"uid": uid, "name": name})
        except Exception as e:
            logger.debug(f"解析关注用户失败: {e}")
            continue

    return follows
