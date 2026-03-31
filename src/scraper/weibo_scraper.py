"""
Selenium微博抓取器

使用Cookie登录微博网页版，抓取好友最新微博和关注列表。
"""

import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from src.auth.login_manager import apply_cookies, load_cookies, WEIBO_HOME_URL
from src.scraper.parser import parse_weibo_cards, parse_follow_list
from src.utils.logger import logger


class WeiboScraper:
    """微博网页版抓取器"""

    def __init__(self):
        self.driver = None

    def start(self):
        """启动浏览器并加载Cookie"""
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })

        cookies = load_cookies()
        if cookies:
            apply_cookies(self.driver, cookies)
            logger.info("浏览器已启动并加载Cookie")
        else:
            logger.error("无法加载Cookie，请先登录")
            raise RuntimeError("Cookie不可用")

    def stop(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("浏览器已关闭")

    def fetch_home_timeline(self, scroll_times=3):
        """
        抓取首页时间线上的微博。
        scroll_times: 向下滚动的次数，越多获取越多微博。
        返回微博列表。
        """
        logger.info("正在抓取首页时间线...")
        self.driver.get(WEIBO_HOME_URL)
        time.sleep(3)

        # 多次滚动加载更多内容
        for i in range(scroll_times):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

        page_source = self.driver.page_source
        weibos = parse_weibo_cards(page_source)
        logger.info(f"首页时间线抓取到 {len(weibos)} 条微博")
        return weibos

    def fetch_user_weibos(self, uid, scroll_times=2):
        """
        抓取指定用户主页的微博。
        uid: 用户UID
        返回微博列表。
        """
        user_url = f"https://weibo.com/u/{uid}"
        logger.info(f"正在抓取用户 {uid} 的微博...")
        self.driver.get(user_url)
        time.sleep(3)

        for i in range(scroll_times):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

        page_source = self.driver.page_source
        weibos = parse_weibo_cards(page_source)
        # 标记来源用户
        for w in weibos:
            if not w.get("user_id"):
                w["user_id"] = str(uid)
        logger.info(f"用户 {uid} 抓取到 {len(weibos)} 条微博")
        return weibos

    def fetch_follow_list(self, uid, max_pages=5):
        """
        抓取指定用户的关注列表。
        uid: 用户UID
        max_pages: 最多抓取几页
        返回关注用户列表 [{"uid": ..., "name": ...}, ...]
        """
        all_follows = []
        for page in range(1, max_pages + 1):
            url = f"https://weibo.com/{uid}/follow?page={page}"
            logger.info(f"正在抓取关注列表第 {page} 页...")
            self.driver.get(url)
            time.sleep(3)

            page_source = self.driver.page_source
            follows = parse_follow_list(page_source)

            if not follows:
                logger.info(f"第 {page} 页无更多关注用户，停止翻页")
                break

            all_follows.extend(follows)
            time.sleep(1)

        logger.info(f"共抓取到 {len(all_follows)} 个关注用户")
        return all_follows
