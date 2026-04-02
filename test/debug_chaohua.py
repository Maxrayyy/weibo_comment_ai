"""
超话功能调试脚本

自动测试：
1. 获取关注的超话列表
2. 抓取第一个超话的帖子
3. 对第一条帖子生成AI评论（不发送，仅展示）
4. 测试发帖接口（不发送，仅展示）
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
from src.chaohua.chaohua_client import ChaohuaClient
from src.utils.rip_provider import get_rip
from src.comment.ai_generator import generate_comment


def main():
    logger.info("=" * 60)
    logger.info("超话功能调试脚本")
    logger.info("=" * 60)

    # ── 初始化 ──
    logger.info("[1/4] 初始化认证...")

    rip = get_rip()
    logger.info(f"公网IP: {rip}")

    cookies = get_valid_cookies()
    if not cookies:
        logger.error("Cookie无效，请重新登录")
        return
    logger.info("Cookie验证通过")

    access_token = get_valid_token()
    if not access_token:
        logger.error("OAuth认证失败")
        return
    uid = get_uid(access_token)
    logger.info(f"OAuth通过 (UID: {uid})")

    logger.info("启动Selenium浏览器...")
    scraper = WeiboScraper()
    scraper.start()
    logger.info("浏览器启动完成")

    raw_cookies = load_cookies()
    client = ChaohuaClient(uid=uid, cookies=raw_cookies, driver=scraper.driver)

    try:
        # ── 测试1: 获取关注的超话 ──
        logger.info("=" * 60)
        logger.info("[2/4] 获取关注的超话列表...")
        topics = client.get_followed_chaohua()

        if not topics:
            logger.error("未获取到超话，请检查Cookie或确认已关注超话")
            return

        logger.info(f"获取到 {len(topics)} 个超话:")
        for i, t in enumerate(topics):
            logger.info(f"  [{i}] {t['name']}  (containerid: {t['containerid']}, "
                        f"粉丝: {t['follow_count']}, 帖子: {t['status_count']})")

        # ── 测试2: 抓取第一个超话的帖子 ──
        logger.info("=" * 60)
        topic = topics[0]
        logger.info(f"[3/4] 抓取超话 [{topic['name']}] 的帖子...")
        weibos = client.get_topic_feed(topic["containerid"], scroll_times=2)

        if not weibos:
            logger.warning("未抓取到帖子，可能页面结构已变化，保存页面源码供分析")
            page_source = scraper.driver.page_source
            debug_path = os.path.join("data", "debug_chaohua_page.html")
            os.makedirs("data", exist_ok=True)
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(page_source)
            logger.info(f"页面源码已保存到 {debug_path}")
        else:
            logger.info(f"抓取到 {len(weibos)} 条帖子:")
            for j, w in enumerate(weibos[:10]):
                logger.info(f"  [{j}] @{w['user_name']}: {w['text'][:80]} (mid: {w['mid']})")

        # ── 测试3: AI生成评论（仅生成不发送） ──
        logger.info("=" * 60)
        if weibos:
            target = weibos[0]
            logger.info(f"[4/4] 测试AI生成评论 (目标: @{target['user_name']}: {target['text'][:80]})")
            comment = generate_comment(target["text"])
            if comment:
                logger.info(f"AI生成评论: {comment}")
                logger.info("(调试模式，不实际发送评论)")
            else:
                logger.warning("AI生成评论失败")
        else:
            logger.info("[4/4] 无帖子可测试评论生成，跳过")

        logger.info("=" * 60)
        logger.info("调试完成!")

    finally:
        scraper.stop()
        logger.info("浏览器已关闭")


if __name__ == "__main__":
    main()
