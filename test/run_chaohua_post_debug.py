"""
超话发帖调试 — 排查"同步到微博"勾选问题
"""

import sys
import os
import time

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
    logger.info("超话发帖调试 — 排查同步问题")
    logger.info("=" * 60)

    cookies = get_valid_cookies()
    if not cookies:
        return
    access_token = get_valid_token()
    if not access_token:
        return
    uid = get_uid(access_token)

    scraper = WeiboScraper()
    scraper.start()

    raw_cookies = load_cookies()
    client = ChaohuaClient(uid=uid, cookies=raw_cookies, driver=scraper.driver)
    driver = scraper.driver

    try:
        topics = client.get_followed_chaohua()
        if not topics:
            return

        topic = topics[0]
        containerid = topic["containerid"]
        topic_url = f"https://weibo.com/p/{containerid}/super_index"

        driver.get(topic_url)
        time.sleep(4)

        # 点击textarea激活发帖区域
        textarea = driver.find_element("css selector", "textarea.W_input")
        textarea.click()
        time.sleep(1)

        # 全面搜索checkbox和label
        all_checkboxes = driver.find_elements("css selector", "input[type=checkbox]")
        logger.info(f"页面所有checkbox: {len(all_checkboxes)}")
        for cb in all_checkboxes:
            name = cb.get_attribute("name") or ""
            checked = cb.get_attribute("checked")
            parent_html = driver.execute_script("return arguments[0].parentElement.innerHTML;", cb)
            logger.info(f"  name={name} checked={checked} parent={parent_html[:100]}")

        # 找同步到微博的label及其关联元素
        sync_labels = driver.find_elements("xpath", "//*[contains(text(),'同步到微博')]")
        logger.info(f"'同步到微博'文字元素: {len(sync_labels)}")
        for label in sync_labels:
            tag = label.tag_name
            parent = driver.execute_script("return arguments[0].parentElement.outerHTML;", label)
            logger.info(f"  <{tag}> parent outerHTML: {parent[:200]}")

        # 尝试点击label本身来取消勾选
        if sync_labels:
            label = sync_labels[0]
            logger.info(f"点击label取消勾选...")
            label.click()
            time.sleep(0.5)

            # 再查checkbox状态
            all_checkboxes2 = driver.find_elements("css selector", "input[type=checkbox]")
            for cb in all_checkboxes2:
                checked = cb.get_attribute("checked")
                logger.info(f"  点击label后 checked={checked}")

        # 截图确认
        driver.save_screenshot("data/debug_after_uncheck2.png")
        logger.info("截图保存: data/debug_after_uncheck2.png")

        # 发帖
        content = "第一次来这个超话，先打个招呼～[太开心]"
        textarea.clear()
        textarea.send_keys(content)
        time.sleep(1)

        submit_btn = driver.find_element(
            "css selector", "a.W_btn_a.btn_30px:not(.W_btn_a_disable)"
        )
        submit_btn.click()
        time.sleep(4)

        new_val = textarea.get_attribute("value") or ""
        if not new_val.strip():
            logger.info(f"超话发帖成功: {content}")
        else:
            logger.warning("发帖结果不确定")

        # 检查主页
        logger.info("检查微博主页...")
        driver.get(f"https://weibo.com/u/{uid}")
        time.sleep(5)
        driver.save_screenshot("data/debug_homepage.png")
        logger.info("主页截图: data/debug_homepage.png")

        page_text = driver.page_source
        if "先打个招呼" in page_text:
            logger.warning("主页发现该帖子 — 同步未成功取消!")
        else:
            logger.info("主页未发现该帖子 — 同步已成功取消")

    finally:
        scraper.stop()
        logger.info("完成")


if __name__ == "__main__":
    main()
