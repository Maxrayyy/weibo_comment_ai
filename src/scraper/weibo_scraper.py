"""
Selenium微博抓取器

使用Cookie登录微博网页版，抓取好友最新微博和关注列表。
"""

import time
import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import random

from src.auth.login_manager import apply_cookies, load_cookies, WEIBO_HOME_URL
from src.scraper.parser import parse_weibo_cards, parse_group_weibo_cards, parse_group_timeline_api, parse_follow_list
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
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        from src.utils.driver_helper import get_chrome_service
        service = get_chrome_service()
        self.driver = webdriver.Chrome(service=service, options=options)
        # 更全面的反检测注入
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
                window.chrome = {runtime: {}};
            """
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

    def _safe_get(self, url, retries=2):
        """安全地加载页面，失败时自动重试"""
        for attempt in range(retries + 1):
            try:
                self.driver.get(url)
                time.sleep(3)
                return True
            except Exception as e:
                logger.warning(f"页面加载失败 ({url})，第{attempt + 1}次: {e}")
                if attempt < retries:
                    time.sleep(5)
                    self._restart_if_needed()
                else:
                    logger.error(f"页面加载最终失败: {url}")
                    return False

    def _restart_if_needed(self):
        """检测浏览器状态，异常时自动重启"""
        try:
            _ = self.driver.current_url
        except Exception:
            logger.warning("浏览器连接丢失，正在重启...")
            try:
                self.driver.quit()
            except Exception:
                pass
            self.start()

    def fetch_home_timeline(self, scroll_times=3):
        """
        抓取首页时间线上的微博。
        scroll_times: 向下滚动的次数，越多获取越多微博。
        返回微博列表。
        """
        logger.info("正在抓取首页时间线...")
        if not self._safe_get(WEIBO_HOME_URL):
            return []

        for i in range(scroll_times):
            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
            except Exception as e:
                logger.warning(f"滚动加载失败: {e}")
                break

        page_source = self.driver.page_source
        weibos = parse_weibo_cards(page_source)
        logger.info(f"首页时间线抓取到 {len(weibos)} 条微博")
        for w in weibos:
            logger.info(f"  [@{w.get('user_name', '?')}] (UID:{w.get('user_id', '?')}) {w.get('text', '')[:100]}")
        return weibos

    def fetch_user_weibos(self, uid, scroll_times=2):
        """
        抓取指定用户主页的微博。
        uid: 用户UID
        返回微博列表。
        """
        user_url = f"https://weibo.com/u/{uid}"
        logger.info(f"正在抓取用户 {uid} 的微博...")
        if not self._safe_get(user_url):
            return []

        # 等待页面渲染
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article"))
            )
        except Exception:
            logger.warning(f"用户 {uid} 主页加载超时，尝试继续...")

        for i in range(scroll_times):
            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
            except Exception as e:
                logger.warning(f"滚动加载失败: {e}")
                break

        page_source = self.driver.page_source
        # 优先使用article解析器（新版微博），回退到旧版解析器
        weibos = parse_group_weibo_cards(page_source)
        if not weibos:
            weibos = parse_weibo_cards(page_source)
        for w in weibos:
            if not w.get("user_id"):
                w["user_id"] = str(uid)
        logger.info(f"用户 {uid} 抓取到 {len(weibos)} 条微博")
        for w in weibos:
            logger.info(f"  [@{w.get('user_name', '?')}] (UID:{w.get('user_id', '?')}) {w.get('text', '')[:100]}")
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
            if not self._safe_get(url):
                logger.warning(f"关注列表第 {page} 页加载失败，停止翻页")
                break

            page_source = self.driver.page_source
            follows = parse_follow_list(page_source)

            if not follows:
                logger.info(f"第 {page} 页无更多关注用户，停止翻页")
                break

            all_follows.extend(follows)
            time.sleep(1)

        logger.info(f"共抓取到 {len(all_follows)} 个关注用户")
        return all_follows

    def fetch_group_timeline(self, gid, scroll_times=3):
        """
        抓取好友圈分组的微博feed。
        优先使用AJAX API直接获取JSON数据（解决长时间运行浏览器的SPA缓存问题），
        失败时回退到HTML解析。
        gid: 好友圈分组ID（URL中的gid参数）
        scroll_times: 向下滚动的次数（仅HTML回退时使用）
        返回微博列表。
        """
        logger.info(f"正在抓取好友圈 (gid={gid})...")

        # 方案一：AJAX API 直接调用
        weibos = self._fetch_group_via_api(gid)
        if weibos:
            logger.info(f"好友圈API抓取到 {len(weibos)} 条微博")
            for w in weibos:
                logger.info(f"  [@{w.get('user_name', '?')}] (UID:{w.get('user_id', '?')}) {w.get('text', '')[:100]}")
            return weibos

        # 方案二：回退到HTML解析
        logger.warning("API调用失败，回退到HTML解析模式")
        return self._fetch_group_via_html(gid, scroll_times)

    def _fetch_group_via_api(self, gid):
        """通过AJAX API获取好友圈微博数据"""
        try:
            # 确保浏览器在微博域下（cookie才能生效）
            current_url = self.driver.current_url
            if "weibo.com" not in current_url:
                self.driver.get("https://weibo.com")
                time.sleep(2)

            # 使用浏览器内置fetch调用API，自动携带cookie
            api_url = f"https://www.weibo.com/ajax/feed/groupstimeline?list_id={gid}&refresh=4&fast_refresh=1&count=25"
            result = self.driver.execute_script(f"""
                try {{
                    var xhr = new XMLHttpRequest();
                    xhr.open('GET', '{api_url}', false);
                    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
                    xhr.send();
                    if (xhr.status === 200) {{
                        return xhr.responseText;
                    }} else {{
                        return 'ERROR:' + xhr.status;
                    }}
                }} catch(e) {{
                    return 'ERROR:' + e.message;
                }}
            """)

            if not result or result.startswith("ERROR:"):
                logger.warning(f"好友圈API请求失败: {result}")
                return []

            import json
            data = json.loads(result)
            weibos = parse_group_timeline_api(data)
            return weibos

        except Exception as e:
            logger.warning(f"好友圈API调用异常: {e}")
            return []

    def _fetch_group_via_html(self, gid, scroll_times):
        """通过HTML解析获取好友圈微博（回退方案）"""
        url = f"https://www.weibo.com/mygroups?gid={gid}"

        try:
            self.driver.execute_cdp_cmd("Network.clearBrowserCache", {})
        except Exception:
            pass

        if not self._safe_get(url):
            return []

        self.driver.refresh()
        time.sleep(8)

        for i in range(scroll_times):
            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(1.5, 3.0))
            except Exception as e:
                logger.warning(f"滚动加载失败: {e}")
                break

        page_source = self.driver.page_source
        weibos = parse_group_weibo_cards(page_source)
        logger.info(f"好友圈HTML抓取到 {len(weibos)} 条微博")
        for w in weibos:
            logger.info(f"  [@{w.get('user_name', '?')}] (UID:{w.get('user_id', '?')}) {w.get('text', '')[:100]}")
        return weibos

    def fetch_mutual_follows(self, uid, max_pages=5):
        """
        抓取互相关注的好友列表。
        uid: 用户UID
        max_pages: 最多抓取几页
        返回互关用户列表 [{"uid": ..., "name": ...}, ...]
        """
        all_follows = []
        for page in range(1, max_pages + 1):
            url = f"https://weibo.com/{uid}/follow?relate=mutual&page={page}"
            logger.info(f"正在抓取互相关注列表第 {page} 页...")
            if not self._safe_get(url):
                logger.warning(f"互关列表第 {page} 页加载失败，停止翻页")
                break

            page_source = self.driver.page_source
            follows = parse_follow_list(page_source)

            if not follows:
                logger.info(f"第 {page} 页无更多互关用户，停止翻页")
                break

            all_follows.extend(follows)
            time.sleep(1)

        logger.info(f"共抓取到 {len(all_follows)} 个互相关注用户")
        for f in all_follows:
            logger.info(f"  互关好友: {f['name']} (UID:{f['uid']})")
        return all_follows
