"""
V3功能调试脚本：表情 + 图片识别

逐项测试：
1. 表情列表获取与缓存
2. 好友圈抓取（含图片URL提取）
3. 超话抓取（含图片URL提取）
4. 纯文本评论生成（带表情注入）
5. 多模态评论生成（文字+图片）
"""

import sys
import os
import time

from dotenv import load_dotenv
load_dotenv()

os.environ["WDM_LOCAL"] = "1"
os.environ["WDM_SSL_VERIFY"] = "0"

from src.utils.logger import logger
from src.auth.login_manager import get_valid_cookies, load_cookies
from src.auth.oauth_manager import get_valid_token, get_uid
from src.scraper.weibo_scraper import WeiboScraper
from src.scraper.api_fetcher import fetch_friends_weibos
from src.chaohua.chaohua_client import ChaohuaClient
from src.emotion.emotion_manager import get_emotion_list, get_emotion_prompt_text
from src.comment.ai_generator import generate_comment
from src.utils.rip_provider import get_rip


def test_emotions(access_token):
    """测试1: 表情列表获取"""
    logger.info("=" * 60)
    logger.info("[TEST 1] 表情列表获取")
    logger.info("=" * 60)

    emotions = get_emotion_list()
    if not emotions:
        logger.error("表情列表获取失败")
        return False

    logger.info(f"获取到 {len(emotions)} 个表情")
    logger.info(f"前20个: {''.join(emotions[:20])}")

    prompt_text = get_emotion_prompt_text()
    logger.info(f"Prompt注入文本: {prompt_text[:150]}...")
    logger.info("[TEST 1] PASS")
    return True


def test_api_images():
    """测试2: API模式图片提取"""
    logger.info("=" * 60)
    logger.info("[TEST 2] API模式图片URL提取")
    logger.info("=" * 60)

    weibos = fetch_friends_weibos(count=20, page=1)
    if not weibos:
        logger.warning("API未抓取到微博，跳过")
        return None

    has_pic = 0
    no_pic = 0
    for w in weibos:
        pic = w.get("pic_url", "")
        if pic:
            has_pic += 1
            logger.info(f"  [有图] @{w['user_name']}: {w['text'][:50]} | pic: {pic[:80]}")
        else:
            no_pic += 1

    logger.info(f"共 {len(weibos)} 条，有图 {has_pic} 条，无图 {no_pic} 条")
    logger.info("[TEST 2] PASS")
    return weibos


def test_chaohua_images(client):
    """测试3: 超话模式图片提取"""
    logger.info("=" * 60)
    logger.info("[TEST 3] 超话模式图片URL提取")
    logger.info("=" * 60)

    topics = client.get_followed_chaohua()
    if not topics:
        logger.warning("无关注超话，跳过")
        return None

    topic = topics[0]
    logger.info(f"抓取超话 [{topic['name']}]...")
    weibos = client.get_topic_feed(topic["containerid"], scroll_times=2)

    if not weibos:
        logger.warning("超话未抓取到帖子")
        return None

    has_pic = 0
    for w in weibos:
        pic = w.get("pic_url", "")
        if pic:
            has_pic += 1
            logger.info(f"  [有图] @{w['user_name']}: {w['text'][:50]} | pic: {pic[:80]}")
        else:
            logger.info(f"  [无图] @{w['user_name']}: {w['text'][:50]}")

    logger.info(f"共 {len(weibos)} 条，有图 {has_pic} 条")
    logger.info("[TEST 3] PASS")
    return weibos


def test_text_comment_with_emotion(weibo_text):
    """测试4: 纯文本评论（带表情注入）"""
    logger.info("=" * 60)
    logger.info("[TEST 4] 纯文本评论生成（带表情注入）")
    logger.info("=" * 60)

    logger.info(f"输入微博: {weibo_text[:80]}")
    comment = generate_comment(weibo_text)
    if comment:
        logger.info(f"生成评论: {comment}")
        has_emotion = "[" in comment and "]" in comment
        logger.info(f"是否包含表情: {has_emotion}")
        logger.info("[TEST 4] PASS")
        return True
    else:
        logger.error("评论生成失败")
        return False


def test_multimodal_comment(weibo_text, pic_url):
    """测试5: 多模态评论（文字+图片）"""
    logger.info("=" * 60)
    logger.info("[TEST 5] 多模态评论生成（文字+图片）")
    logger.info("=" * 60)

    logger.info(f"输入微博: {weibo_text[:80]}")
    logger.info(f"输入图片: {pic_url[:100]}")
    comment = generate_comment(weibo_text, pic_url=pic_url)
    if comment:
        logger.info(f"生成评论: {comment}")
        logger.info("[TEST 5] PASS")
        return True
    else:
        logger.error("多模态评论生成失败（可能模型不支持图片，回退测试纯文本）")
        comment2 = generate_comment(weibo_text)
        if comment2:
            logger.info(f"纯文本回退评论: {comment2}")
        return False


def main():
    logger.info("=" * 60)
    logger.info("V3 功能验证: 表情 + 图片识别")
    logger.info("=" * 60)

    # 初始化
    rip = get_rip()
    logger.info(f"公网IP: {rip}")

    cookies = get_valid_cookies()
    if not cookies:
        logger.error("Cookie无效")
        return

    access_token = get_valid_token()
    if not access_token:
        logger.error("OAuth失败")
        return
    uid = get_uid(access_token)
    logger.info(f"UID: {uid}")

    # TEST 1: 表情
    test_emotions(access_token)

    # TEST 2: API图片
    api_weibos = test_api_images()

    # TEST 3: 超话图片（需要Selenium）
    logger.info("启动Selenium...")
    scraper = WeiboScraper()
    scraper.start()

    raw_cookies = load_cookies()
    client = ChaohuaClient(uid=uid, cookies=raw_cookies, driver=scraper.driver)

    try:
        chaohua_weibos = test_chaohua_images(client)

        # 收集测试素材：找一条有图和一条无图的微博
        all_weibos = (api_weibos or []) + (chaohua_weibos or [])
        text_weibo = None
        pic_weibo = None
        for w in all_weibos:
            if w.get("pic_url") and not pic_weibo:
                pic_weibo = w
            if not w.get("pic_url") and not text_weibo:
                text_weibo = w
            if text_weibo and pic_weibo:
                break

        # TEST 4: 纯文本评论
        if text_weibo:
            test_text_comment_with_emotion(text_weibo["text"])
        elif all_weibos:
            test_text_comment_with_emotion(all_weibos[0]["text"])
        else:
            logger.warning("无微博可测试评论生成")

        # TEST 5: 多模态评论
        if pic_weibo:
            test_multimodal_comment(pic_weibo["text"], pic_weibo["pic_url"])
        else:
            logger.warning("[TEST 5] 未找到有图微博，跳过多模态测试")

    finally:
        scraper.stop()

    logger.info("=" * 60)
    logger.info("全部测试完成!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
