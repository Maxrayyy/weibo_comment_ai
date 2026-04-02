"""
超话发帖 — 一次性测试

向关注的第一个超话发一条帖子。
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

os.environ["WDM_LOCAL"] = "1"
os.environ["WDM_SSL_VERIFY"] = "0"

from src.utils.logger import logger
from src.auth.login_manager import get_valid_cookies, load_cookies
from src.auth.oauth_manager import get_valid_token, get_uid
from src.scraper.weibo_scraper import WeiboScraper
from src.chaohua.chaohua_client import ChaohuaClient


def main():
    logger.info("=" * 60)
    logger.info("超话发帖 — 一次性测试")
    logger.info("=" * 60)

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

    try:
        topics = client.get_followed_chaohua()
        if not topics:
            logger.error("未获取到关注的超话")
            return

        topic = topics[0]
        logger.info(f"目标超话: [{topic['name']}] (containerid: {topic['containerid']})")

        content = "第一次来这个超话，先打个招呼～[太开心]"
        logger.info(f"发帖内容: {content}")

        success = client.post_to_topic(topic["containerid"], content)
        if success:
            logger.info("发帖成功!")
        else:
            logger.warning("发帖可能失败，查看上方日志排查原因")

    finally:
        scraper.stop()
        logger.info("浏览器已关闭")


if __name__ == "__main__":
    main()
