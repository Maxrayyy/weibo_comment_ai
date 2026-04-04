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
        # 跳过用户头像（头像路径包含 /avatar/ 或 headicon 或 default_avatar）
        if "avatar" in src or "headicon" in src or "default" in src:
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


# ====== 评论收件箱页面解析 ======

def parse_comment_inbox(html):
    """
    解析评论收件箱页面（https://www.weibo.com/comment/inbox）。
    返回评论列表，每条评论包含：
    {
        "comment_id": 评论ID,
        "comment_text": 评论内容,
        "comment_user_id": 评论者UID,
        "comment_user_name": 评论者昵称,
        "weibo_mid": 微博ID（从URL提取）,
        "weibo_text": 微博原文,
        "reply_comment_text": 被回复的评论内容（楼中楼，可选）,
        "reply_comment_user": 被回复者昵称（可选）,
        "created_at": 评论时间文本,
    }
    """
    soup = BeautifulSoup(html, "html.parser")
    comments = []

    # 每个评论卡片是一个 wbpro-scroller-item
    cards = soup.find_all("div", class_="wbpro-scroller-item")
    if not cards:
        # 备选：直接找包含评论内容的面板
        cards = soup.find_all("div", class_=re.compile(r"_wrap_1bd52"))

    for card in cards:
        try:
            comment = _extract_comment_from_card(card)
            if comment and comment.get("comment_id") and comment.get("comment_text"):
                comments.append(comment)
        except Exception as e:
            logger.debug(f"解析评论卡片失败: {e}")
            continue

    return comments


def _extract_comment_from_card(card):
    """从评论收件箱页面的单个卡片中提取评论信息"""
    comment = {}

    # 1. 提取评论者昵称和UID
    # 昵称在 _h3_ 容器的链接中
    name_elem = card.find("div", class_=re.compile(r"_h3_"))
    if name_elem:
        a = name_elem.find("a")
        if a:
            comment["comment_user_name"] = a.get_text(strip=True)
            href = a.get("href", "")
            uid_match = re.search(r"/u/(\d+)", href)
            comment["comment_user_id"] = uid_match.group(1) if uid_match else ""
    if not comment.get("comment_user_name"):
        # 备选：从 avatar 的 usercard 属性获取
        avatar = card.find("div", class_="woo-avatar-main")
        if avatar:
            comment["comment_user_id"] = avatar.get("usercard", "")
        comment.setdefault("comment_user_name", "")
        comment.setdefault("comment_user_id", "")

    # 2. 提取评论时间和评论ID（从时间链接的URL中提取cid）
    from_elem = card.find("div", class_=re.compile(r"_from_"))
    if from_elem:
        time_link = from_elem.find("a")
        if time_link:
            comment["created_at"] = time_link.get_text(strip=True)
            href = time_link.get("href", "")
            # 提取 cid 参数作为评论ID
            cid_match = re.search(r"cid=(\d+)", href)
            comment["comment_id"] = cid_match.group(1) if cid_match else ""
            # 提取微博路径中的bid -> mid
            bid_match = re.search(r"weibo\.com/\d+/(\w+)", href)
            if bid_match:
                comment["weibo_mid"] = bid_to_mid(bid_match.group(1))
    comment.setdefault("comment_id", "")
    comment.setdefault("created_at", "")
    comment.setdefault("weibo_mid", "")

    # 3. 提取评论内容
    # 评论文本在 _wbtext_ 且带 _textImg_ 的 div 中（第一个是评论内容）
    wbtext_elems = card.find_all("div", class_=re.compile(r"_wbtext_.*_textImg_|_textImg_.*_wbtext_"))
    if not wbtext_elems:
        wbtext_elems = card.find_all("div", class_=re.compile(r"_wbtext_"))

    raw_text = ""
    is_reply = False
    if wbtext_elems:
        first_text_elem = wbtext_elems[0]
        raw_text = first_text_elem.get_text(strip=True)

        # 检查是否是楼中楼回复（文本以"回复@xxx:"开头）
        if raw_text.startswith("回复"):
            is_reply = True
            # 提取"回复@xxx:实际内容"中的实际内容
            colon_match = re.search(r"[:：]", raw_text[2:])  # 跳过"回复"两字
            if colon_match:
                comment["comment_text"] = raw_text[2 + colon_match.end():].strip()
            else:
                comment["comment_text"] = raw_text
        else:
            comment["comment_text"] = raw_text
    comment.setdefault("comment_text", "")

    # 4. 提取被回复的评论（楼中楼场景）和原微博内容
    repeat_box = card.find("div", class_=re.compile(r"_repeatbox_|_repeatbgbox_"))
    comment["reply_comment_text"] = None
    comment["reply_comment_user"] = None
    comment["weibo_text"] = ""

    if repeat_box:
        # 检查是否有楼中楼的被回复评论
        reply_comment_elem = repeat_box.find("div", class_=re.compile(r"_replyComment_"))
        if reply_comment_elem:
            # 被回复者昵称
            reply_name = reply_comment_elem.find("span", class_=re.compile(r"_replyCname_"))
            if reply_name:
                name_text = reply_name.get_text(strip=True)
                # 去掉 @ 和 : 符号
                name_text = name_text.replace("@", "").rstrip(":：").strip()
                comment["reply_comment_user"] = name_text

            # 被回复的评论内容（第二个span）
            spans = reply_comment_elem.find_all("span")
            if len(spans) >= 2:
                comment["reply_comment_text"] = spans[-1].get_text(strip=True)

        # 原微博内容（在引用卡片中）
        weibo_text_elem = repeat_box.find("div", class_=re.compile(r"_messText_|_text_3pz7a"))
        if weibo_text_elem:
            comment["weibo_text"] = weibo_text_elem.get_text(strip=True)
        else:
            # 备选：找 feed-card-repost 中的文本
            feed_card = repeat_box.find("div", class_="feed-card-repost")
            if feed_card:
                text_div = feed_card.find("div", class_=re.compile(r"_text_|_cut"))
                if text_div:
                    comment["weibo_text"] = text_div.get_text(strip=True)

    return comment


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
