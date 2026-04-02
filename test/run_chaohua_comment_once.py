"""
超话评论 — 一次性执行

抓取关注的所有超话帖子，AI生成评论并发布。
跳过已评论过的帖子。
"""

import sys
import os
import random
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

os.environ["WDM_LOCAL"] = "1"
os.environ["WDM_SSL_VERIFY"] = "0"

from src.utils.logger import logger
from src.utils.config_loader import config
from src.auth.login_manager import get_valid_cookies, load_cookies
from src.auth.oauth_manager import get_valid_token, get_uid
from src.scraper.weibo_scraper import WeiboScraper
from src.chaohua.chaohua_client import ChaohuaClient
from src.comment.ai_generator import generate_comment
from src.comment.publisher import publish_comment
from src.storage.record_store import record_store
from src.utils.rip_provider import get_rip


def main():
    logger.info("=" * 60)
    logger.info("超话评论 — 一次性执行")
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

    scraper = WeiboScraper()
    scraper.start()
    logger.info("浏览器启动")

    raw_cookies = load_cookies()
    client = ChaohuaClient(uid=uid, cookies=raw_cookies, driver=scraper.driver)

    total_success = 0

    try:
        # 获取关注的超话
        topics = client.get_followed_chaohua()
        if not topics:
            logger.error("未获取到关注的超话")
            return

        logger.info(f"共 {len(topics)} 个关注超话")
        for i, t in enumerate(topics):
            logger.info(f"  [{i}] {t['name']} (粉丝:{t['follow_count']})")

        # 遍历每个超话
        for topic in topics:
            name = topic["name"]
            containerid = topic["containerid"]
            logger.info("=" * 60)
            logger.info(f"抓取超话 [{name}] 的帖子...")

            weibos = client.get_topic_feed(containerid, scroll_times=2)
            if not weibos:
                logger.info(f"[{name}] 无帖子")
                continue

            logger.info(f"[{name}] 抓取到 {len(weibos)} 条帖子")

            for w in weibos:
                mid = w.get("mid", "")
                text = w.get("text", "")
                user_name = w.get("user_name", "?")
                pic_url = w.get("pic_url", "")

                if not mid or not text:
                    continue

                # 跳过自己的帖子
                if w.get("user_id") == str(uid):
                    logger.info(f"  跳过自己的帖子: {text[:40]}")
                    continue

                # 跳过已评论
                if record_store.is_commented(mid):
                    logger.info(f"  已评论过，跳过: @{user_name}: {text[:40]}")
                    continue

                # 跳过转发
                if config.skip_repost and w.get("is_repost"):
                    logger.info(f"  转发微博，跳过: @{user_name}: {text[:40]}")
                    continue

                logger.info(f"  目标: @{user_name}: {text[:60]}")
                if pic_url:
                    logger.info(f"  图片: {pic_url[:80]}")

                # AI生成评论
                comment = generate_comment(text, pic_url=pic_url if pic_url else None)
                if not comment:
                    logger.warning(f"  评论生成失败，跳过")
                    continue

                logger.info(f"  生成评论: {comment}")

                # 随机延迟后发布
                delay = random.randint(config.comment_delay_min, config.comment_delay_max)
                logger.info(f"  等待 {delay}s 后发布...")
                time.sleep(delay)

                result = publish_comment(mid, comment, rip)
                if result:
                    record_store.add_record(mid, comment, user_name, comment_id=result.get("id"))
                    total_success += 1
                    logger.info(f"  评论成功! (cid: {result.get('id')})")
                else:
                    logger.warning(f"  评论失败")

            # 超话之间间隔
            time.sleep(random.uniform(2, 5))

        logger.info("=" * 60)
        logger.info(f"全部完成! 共成功评论 {total_success} 条")

    finally:
        scraper.stop()
        logger.info("浏览器已关闭")


if __name__ == "__main__":
    main()
