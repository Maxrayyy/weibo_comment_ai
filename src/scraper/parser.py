"""
微博页面HTML解析器

使用BeautifulSoup解析微博网页版HTML，提取微博和用户信息。
"""

import re
from bs4 import BeautifulSoup

from src.utils.logger import logger


def _extract_first_pic(element):
    """
    从页面元素中提取第一张微博图片URL。
    将缩略图URL转为中等尺寸（mw690）。
    返回图片URL字符串，无图返回空字符串。
    """
    imgs = element.find_all("img", src=re.compile(r"sinaimg\.cn"))
    for img in imgs:
        src = img.get("src", "")
        # 跳过表情图片（表情域名为 face.t.sinajs.cn 或尺寸很小的图）
        if "face" in src or "emoticon" in src:
            continue
        # 将任意尺寸替换为 mw690（中等偏大，适合模型识别）
        pic_url = re.sub(
            r"(sinaimg\.cn/)(thumbnail|bmiddle|orj360|orj480|thumb150|square|small|mw\d+|large)",
            r"\1mw690",
            src,
        )
        # 确保是https
        if pic_url.startswith("//"):
            pic_url = "https:" + pic_url
        elif pic_url.startswith("http://"):
            pic_url = pic_url.replace("http://", "https://", 1)
        return pic_url
    return ""


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

    # 提取第一张图片URL
    weibo["pic_url"] = _extract_first_pic(card)

    return weibo


# ====== bid <-> mid 转换 ======

_BASE62_ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'


def bid_to_mid(bid):
    """微博bid(base62)转mid(数字ID)"""
    mid = ''
    bid = bid[::-1]
    for i in range(0, len(bid), 4):
        chunk = bid[i:i + 4][::-1]
        num = 0
        for c in chunk:
            num = num * 62 + _BASE62_ALPHABET.index(c)
        mid = str(num).zfill(7) + mid
    return mid.lstrip('0') or '0'


# ====== 好友圈页面解析 ======

def parse_group_weibo_cards(html):
    """
    解析好友圈分组页面（Vue SPA）的微博内容。
    页面结构：每条微博是一个 <article> 标签。
    返回微博列表，格式同 parse_weibo_cards。
    """
    soup = BeautifulSoup(html, "html.parser")
    weibos = []

    articles = soup.find_all("article")
    for article in articles:
        try:
            weibo = _extract_weibo_from_article(article)
            if weibo and weibo.get("mid") and weibo.get("text"):
                weibos.append(weibo)
        except Exception as e:
            logger.debug(f"解析好友圈微博卡片失败: {e}")
            continue

    return weibos


def _extract_weibo_from_article(article):
    """从好友圈页面的article元素中提取微博信息"""
    weibo = {}

    # 提取微博详情链接 → bid → mid
    detail_link = article.find("a", href=re.compile(r"weibo\.com/\d+/\w+"))
    if detail_link:
        href = detail_link.get("href", "")
        match = re.search(r"weibo\.com/\d+/(\w+)", href)
        if match:
            weibo["mid"] = bid_to_mid(match.group(1))
    if not weibo.get("mid"):
        return None

    # 提取用户信息（nick区域的链接）
    nick_elem = article.find(class_=re.compile(r"_nick_"))
    if nick_elem:
        a = nick_elem.find("a") if nick_elem.name != "a" else nick_elem
        if a:
            weibo["user_name"] = a.get_text(strip=True)
            href = a.get("href", "")
            uid_match = re.search(r"/u/(\d+)", href)
            weibo["user_id"] = uid_match.group(1) if uid_match else ""
    weibo.setdefault("user_name", "")
    weibo.setdefault("user_id", "")

    # 提取正文
    text_elem = article.find(class_=re.compile(r"_wbtext_"))
    if text_elem:
        for a in text_elem.find_all("a"):
            if "展开" in a.get_text() or "收起" in a.get_text():
                a.decompose()
        weibo["text"] = text_elem.get_text(strip=True)
    else:
        weibo["text"] = ""

    # 判断是否转发（存在引用区域）
    repost_elem = article.find(class_=re.compile(r"wbpro-feed-repost|_repost_"))
    weibo["is_repost"] = repost_elem is not None

    # 提取发布时间
    time_link = article.find("a", href=re.compile(r"weibo\.com/\d+/\w+"))
    weibo["created_at"] = time_link.get_text(strip=True) if time_link else ""

    # 提取第一张图片URL
    weibo["pic_url"] = _extract_first_pic(article)

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
