"""
Selenium手动登录 + Cookie持久化管理

流程：
1. 检查本地Cookie是否存在且有效
2. 无效则启动浏览器让用户手动登录
3. 登录成功后保存Cookie到本地文件
"""

import json
import os
import time

from selenium import webdriver

from src.utils.logger import logger

COOKIE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "cookies.json"
)

WEIBO_LOGIN_URL = "https://passport.weibo.com/sso/signin"
WEIBO_HOME_URL = "https://weibo.com"


def _create_driver(headless=False):
    """创建Chrome浏览器实例"""
    from src.utils.driver_helper import get_chrome_service, get_chrome_options
    options = get_chrome_options(headless=headless)
    service = get_chrome_service()
    driver = webdriver.Chrome(service=service, options=options)
    # 移除webdriver特征
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver


def save_cookies(driver):
    """将浏览器Cookie保存到本地JSON文件"""
    cookies = driver.get_cookies()
    os.makedirs(os.path.dirname(COOKIE_PATH), exist_ok=True)
    with open(COOKIE_PATH, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    logger.info(f"Cookie已保存到 {COOKIE_PATH}，共{len(cookies)}条")


def load_cookies():
    """从本地文件加载Cookie"""
    if not os.path.exists(COOKIE_PATH):
        return None
    with open(COOKIE_PATH, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    logger.info(f"已加载本地Cookie，共{len(cookies)}条")
    return cookies


def apply_cookies(driver, cookies):
    """将Cookie应用到浏览器"""
    driver.get(WEIBO_HOME_URL)
    time.sleep(2)
    for cookie in cookies:
        # 移除可能导致问题的字段
        for key in ["sameSite", "expiry", "httpOnly", "secure"]:
            cookie.pop(key, None)
        try:
            driver.add_cookie(cookie)
        except Exception:
            pass


def verify_login(driver):
    """验证Cookie是否有效（是否处于登录状态）"""
    driver.get(WEIBO_HOME_URL)
    time.sleep(3)
    current_url = driver.current_url
    page_source = driver.page_source
    # 如果被重定向到登录页或页面包含登录按钮，说明未登录
    if "passport" in current_url or "login" in current_url:
        return False
    if "立即登录" in page_source and "我的首页" not in page_source:
        return False
    logger.info("Cookie验证成功，当前处于登录状态")
    return True


def manual_login():
    """
    启动浏览器让用户手动登录微博。
    登录成功后自动保存Cookie。
    返回保存的Cookie列表。
    """
    logger.info("启动浏览器，请手动完成微博登录...")
    driver = _create_driver(headless=False)
    try:
        driver.get(WEIBO_LOGIN_URL)
        logger.info("=" * 50)
        logger.info("请在浏览器中完成登录（包括验证码等）")
        logger.info("登录成功后页面会自动跳转，程序将自动检测")
        logger.info("=" * 50)

        # 等待用户登录成功，最长等待5分钟
        timeout = 300
        start = time.time()
        while time.time() - start < timeout:
            current_url = driver.current_url
            # 登录成功后通常会跳转到微博首页
            if "weibo.com" in current_url and "passport" not in current_url and "login" not in current_url:
                logger.info("检测到登录成功！")
                time.sleep(2)
                save_cookies(driver)
                return load_cookies()
            time.sleep(2)

        logger.error("登录超时（5分钟），请重试")
        return None
    finally:
        driver.quit()


def get_valid_cookies():
    """
    获取有效的Cookie。
    优先使用本地保存的Cookie，无效则触发手动登录。
    返回Cookie列表，失败返回None。
    """
    cookies = load_cookies()
    if cookies:
        logger.info("检测本地Cookie有效性...")
        driver = _create_driver(headless=True)
        try:
            apply_cookies(driver, cookies)
            if verify_login(driver):
                return cookies
            else:
                logger.warning("本地Cookie已过期，需要重新登录")
        finally:
            driver.quit()

    if os.environ.get("DOCKER_ENV") == "1":
        logger.error("Docker环境下无法手动登录，请在本地登录后将 data/cookies.json 挂载到容器")
        return None

    return manual_login()
