"""
调试：抓取超话页面发帖时的实际网络请求

通过Selenium Performance Log捕获超话页面的API请求，
分析发帖接口的真实URL和参数。
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

os.environ["WDM_LOCAL"] = "1"
os.environ["WDM_SSL_VERIFY"] = "0"

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from src.utils.logger import logger
from src.auth.login_manager import CHROMEDRIVER_PATH, load_cookies, apply_cookies


def main():
    logger.info("=" * 60)
    logger.info("调试：抓取超话页面网络请求")
    logger.info("=" * 60)

    # 启动带Performance Log的浏览器
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    # 启用performance log
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    cookies = load_cookies()
    if not cookies:
        logger.error("无Cookie")
        driver.quit()
        return

    # 加载cookie
    driver.get("https://weibo.com")
    time.sleep(2)
    for cookie in cookies:
        for key in ["sameSite", "expiry", "httpOnly", "secure"]:
            cookie.pop(key, None)
        try:
            driver.add_cookie(cookie)
        except Exception:
            pass

    # 访问超话页面
    containerid = "1008081d6757aff7115975446d7771b79452a3"
    topic_url = f"https://weibo.com/p/{containerid}/super_index"
    logger.info(f"访问超话页面: {topic_url}")
    driver.get(topic_url)
    time.sleep(5)

    # 截图看看页面状态
    driver.save_screenshot("data/debug_chaohua_page.png")
    logger.info("页面截图已保存到 data/debug_chaohua_page.png")

    # 收集页面上所有与发帖相关的元素
    page_source = driver.page_source

    # 查找发帖框/发帖按钮
    logger.info("页面URL: " + driver.current_url)
    logger.info(f"页面标题: {driver.title}")

    # 查找所有 textarea 和 发送按钮
    textareas = driver.find_elements("css selector", "textarea")
    logger.info(f"找到 {len(textareas)} 个textarea")
    for ta in textareas:
        logger.info(f"  textarea placeholder: {ta.get_attribute('placeholder')}")

    buttons = driver.find_elements("css selector", "button, a.W_btn_a, a[node-type='submit']")
    logger.info(f"找到 {len(buttons)} 个按钮")
    for btn in buttons[:10]:
        logger.info(f"  按钮: {btn.text} | class: {btn.get_attribute('class')}")

    # 检查performance log，找已有的API请求
    logs = driver.get_log("performance")
    api_urls = set()
    for entry in logs:
        try:
            msg = json.loads(entry["message"])["message"]
            if msg["method"] == "Network.requestWillBeSent":
                url = msg["params"]["request"]["url"]
                if "ajax" in url or "api" in url or "huati" in url or "statuses" in url:
                    api_urls.add(url)
        except Exception:
            pass

    logger.info(f"捕获到 {len(api_urls)} 个相关API请求:")
    for url in sorted(api_urls):
        logger.info(f"  {url[:150]}")

    # 保存页面源码
    with open("data/debug_chaohua_post_page.html", "w", encoding="utf-8") as f:
        f.write(page_source)
    logger.info("页面源码保存到 data/debug_chaohua_post_page.html")

    driver.quit()
    logger.info("完成")


if __name__ == "__main__":
    main()
