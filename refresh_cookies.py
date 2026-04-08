"""
刷新微博Cookie

打开浏览器访问微博：
- Cookie有效：自动刷新并保存（微博会续期Cookie）
- Cookie过期：弹出登录页，手动登录后自动保存
"""

import json
import os
import sys
import time

from dotenv import load_dotenv
load_dotenv()

os.environ["WDM_LOCAL"] = "1"
os.environ["WDM_SSL_VERIFY"] = "0"

from src.utils.driver_helper import get_chrome_service, get_chrome_options
from src.auth.login_manager import COOKIE_PATH, WEIBO_HOME_URL, WEIBO_LOGIN_URL

from selenium import webdriver


def main():
    # 加载已有Cookie
    old_cookies = []
    if os.path.exists(COOKIE_PATH):
        with open(COOKIE_PATH, "r", encoding="utf-8") as f:
            old_cookies = json.load(f)
        print(f"已加载本地Cookie，共{len(old_cookies)}条")
    else:
        print("未找到本地Cookie文件，将直接打开登录页")

    # 启动浏览器（非headless，用户可见）
    options = get_chrome_options(headless=False)
    service = get_chrome_service()
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    try:
        # 先访问weibo.com再注入Cookie
        driver.get(WEIBO_HOME_URL)
        time.sleep(2)

        if old_cookies:
            for cookie in old_cookies:
                for key in ["sameSite", "expiry", "httpOnly", "secure"]:
                    cookie.pop(key, None)
                try:
                    driver.add_cookie(cookie)
                except Exception:
                    pass
            # 刷新页面让Cookie生效
            driver.get(WEIBO_HOME_URL)
            time.sleep(3)

        # 检查是否已登录
        current_url = driver.current_url
        page_source = driver.page_source

        if "passport" not in current_url and "login" not in current_url and "我的首页" in page_source:
            print("Cookie仍然有效，正在刷新保存...")
            _save_cookies(driver)
            print("完成！Cookie已刷新，可以关闭窗口。")
            time.sleep(3)
            return

        # Cookie过期，跳转登录页
        print("=" * 50)
        print("Cookie已过期，请在浏览器中手动登录")
        print("登录成功后程序会自动检测并保存")
        print("=" * 50)
        driver.get(WEIBO_LOGIN_URL)

        # 等待登录成功，最长5分钟
        timeout = 300
        start = time.time()
        while time.time() - start < timeout:
            current_url = driver.current_url
            if "weibo.com" in current_url and "passport" not in current_url and "login" not in current_url:
                print("检测到登录成功！")
                time.sleep(2)
                _save_cookies(driver)
                print("完成！Cookie已保存，可以关闭窗口。")
                time.sleep(3)
                return
            time.sleep(2)

        print("登录超时（5分钟），请重试")
        sys.exit(1)

    finally:
        driver.quit()


def _save_cookies(driver):
    cookies = driver.get_cookies()
    os.makedirs(os.path.dirname(COOKIE_PATH), exist_ok=True)
    with open(COOKIE_PATH, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"Cookie已保存到 {COOKIE_PATH}，共{len(cookies)}条")


if __name__ == "__main__":
    main()
