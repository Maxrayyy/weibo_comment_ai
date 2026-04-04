"""调试脚本：抓取评论收件箱页面HTML，分析页面结构"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

os.environ["WDM_LOCAL"] = "1"
os.environ["WDM_SSL_VERIFY"] = "0"

from src.utils.logger import logger
from src.auth.login_manager import get_valid_cookies
from src.scraper.weibo_scraper import WeiboScraper

COMMENT_INBOX_URL = "https://www.weibo.com/comment/inbox"


def main():
    cookies = get_valid_cookies()
    if not cookies:
        logger.error("Cookie无效")
        return

    scraper = WeiboScraper()
    scraper.start()

    try:
        logger.info(f"访问评论收件箱: {COMMENT_INBOX_URL}")
        scraper.driver.get(COMMENT_INBOX_URL)
        time.sleep(5)

        # 截图
        scraper.driver.save_screenshot("data/debug_comment_inbox.png")
        logger.info("截图已保存: data/debug_comment_inbox.png")

        # 保存完整HTML
        html = scraper.driver.page_source
        with open("data/debug_comment_inbox.html", "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"HTML已保存: data/debug_comment_inbox.html ({len(html)} 字符)")

        # 尝试滚动加载更多
        scraper.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

        # 再次截图和保存
        scraper.driver.save_screenshot("data/debug_comment_inbox_scrolled.png")
        html2 = scraper.driver.page_source
        with open("data/debug_comment_inbox_scrolled.html", "w", encoding="utf-8") as f:
            f.write(html2)
        logger.info(f"滚动后HTML已保存 ({len(html2)} 字符)")

    finally:
        scraper.stop()

    logger.info("完成，请查看 data/ 目录下的截图和HTML文件")


if __name__ == "__main__":
    main()
