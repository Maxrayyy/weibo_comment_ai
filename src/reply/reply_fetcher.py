"""
获取收到的评论

通过Selenium抓取评论收件箱页面，解析评论数据。
"""

import time
import random

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.scraper.parser import parse_comment_inbox
from src.utils.logger import logger

COMMENT_INBOX_URL = "https://www.weibo.com/comment/inbox"


def fetch_comments_to_me(driver, scroll_times=2):
    """
    通过Selenium抓取评论收件箱页面，获取收到的评论列表。

    参数：
        driver: Selenium WebDriver 实例
        scroll_times: 页面滚动次数（加载更多评论）

    返回：
        评论列表 [{
            "comment_id": str,
            "comment_text": str,
            "comment_user_id": str,
            "comment_user_name": str,
            "weibo_mid": str,
            "weibo_text": str,
            "reply_comment_text": str or None,
            "reply_comment_user": str or None,
            "created_at": str,
        }, ...]
    """
    try:
        logger.info(f"访问评论收件箱: {COMMENT_INBOX_URL}")
        driver.get(COMMENT_INBOX_URL)
        time.sleep(4)

        # 等待评论卡片加载
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.wbpro-scroller-item"))
            )
        except Exception:
            logger.warning("评论收件箱页面加载超时，尝试继续解析...")

        # 滚动加载更多评论
        for i in range(scroll_times):
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(1.5, 3.0))
            except Exception as e:
                logger.warning(f"滚动加载失败: {e}")
                break

        # 解析页面HTML
        html = driver.page_source
        comments = parse_comment_inbox(html)

        if not comments:
            logger.info("没有获取到评论")
            return []

        logger.info(f"从评论收件箱获取到 {len(comments)} 条评论")
        return comments

    except Exception as e:
        logger.error(f"获取评论收件箱异常: {e}")
        return []
