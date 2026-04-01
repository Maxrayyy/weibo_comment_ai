"""
微博超话客户端（PC Cookie方案）

基于PC端Cookie实现超话相关操作，无需手机抓包：
- 获取关注的超话列表（weibo.com Ajax API）
- 超话签到（huati.weibo.com）
- 获取超话帖子（Selenium DOM解析）
- 超话发帖（huati.weibo.com）
"""

import re
import time
import random

import requests
from bs4 import BeautifulSoup

from src.utils.logger import logger

# PC端Ajax接口
TOPIC_LIST_URL = "https://weibo.com/ajax/profile/topicContent"

# huati.weibo.cn 接口
CHECKIN_URL = "http://i.huati.weibo.com/aj/super/checkin"
SEND_CONTENT_URL = "http://i.huati.weibo.com/pcpage/operation/publisher/sendcontent"


class ChaohuaClient:
    """微博超话客户端（PC Cookie方案）"""

    def __init__(self, uid, cookies, driver=None):
        """
        参数：
            uid: 用户UID
            cookies: PC端Cookie列表（同login_manager中的格式）
            driver: Selenium WebDriver实例（用于帖子抓取和签到）
        """
        self.uid = str(uid)
        self.driver = driver

        # 构建requests Session
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            "Referer": "https://weibo.com/",
        })
        # 加载cookies到session（.weibo.com域名的cookie适用于子域名）
        for cookie in cookies:
            self.session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain", ".weibo.com"),
                path=cookie.get("path", "/"),
            )

        logger.info(f"超话客户端初始化完成 (UID: {self.uid})")

    def get_followed_chaohua(self):
        """
        获取用户关注的所有超话列表。
        返回: [{"name": str, "containerid": str, "oid": str, "follow_count": int, "status_count": int}, ...]
        """
        try:
            resp = self.session.get(
                TOPIC_LIST_URL,
                params={"tabid": "231093_-_chaohua", "uid": self.uid},
                timeout=15,
            )
            data = resp.json()

            if data.get("ok") != 1:
                logger.error(f"获取超话列表失败: {data}")
                return []

            raw_list = data.get("data", {}).get("list", [])
            topics = []
            for item in raw_list:
                oid = item.get("oid", "")
                containerid = oid.split(":")[-1] if ":" in oid else oid
                topics.append({
                    "name": item.get("topic_name", item.get("title", "")),
                    "containerid": containerid,
                    "oid": oid,
                    "follow_count": item.get("follow_count", 0),
                    "status_count": item.get("status_count", 0),
                    "following": item.get("following", False),
                })

            logger.info(f"获取到 {len(topics)} 个关注超话")
            return topics

        except Exception as e:
            logger.error(f"获取超话列表异常: {e}")
            return []

    def sign_in(self, containerid):
        """
        对单个超话执行签到。
        通过Selenium在超话页面上下文中调用签到API。

        参数:
            containerid: 超话containerid
        返回: True/False/None(已签到)
        """
        if not self.driver:
            logger.error("签到需要Selenium driver")
            return False

        try:
            topic_url = f"https://weibo.com/p/{containerid}/super_index"
            self.driver.get(topic_url)
            time.sleep(3)

            # 检查是否已签到（页面元素分析）
            page_source = self.driver.page_source
            if "已签到" in page_source:
                logger.info(f"超话 {containerid} 今日已签到")
                return None  # 已签到

            # 通过页面中的action-data提取签到API参数
            # 签到按钮格式: action-data="api=http://i.huati.weibo.com/aj/super/checkin&...&id=containerid"
            checkin_match = re.search(
                r'action-data="[^"]*api=http://i\.huati\.weibo\.com/aj/super/checkin[^"]*id=([^&"]+)',
                page_source,
            )

            if not checkin_match:
                # 尝试直接用containerid签到
                logger.info(f"未找到签到按钮，尝试直接签到")

            # 通过Selenium的fetch发起签到请求（保持cookie上下文）
            result = self.driver.execute_script(f"""
                try {{
                    const formData = new URLSearchParams();
                    formData.append('id', '{containerid}');
                    const resp = await fetch('{CHECKIN_URL}', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                        body: formData.toString()
                    }});
                    const text = await resp.text();
                    return text;
                }} catch(e) {{
                    return JSON.stringify({{error: e.message}});
                }}
            """)

            if result:
                logger.debug(f"签到响应: {result[:200]}")
                if '"code":100000' in result or "已签到" in result or "签到成功" in result:
                    return True
                if "已签" in result:
                    return None

            # 备选：尝试用requests直接调用（cookie带.weibo.com域名可能对huati子域名有效）
            try:
                resp = self.session.post(
                    CHECKIN_URL,
                    data={"id": containerid},
                    headers={"Referer": topic_url},
                    timeout=15,
                )
                resp_data = resp.json()
                logger.debug(f"requests签到响应: {resp_data}")
                if resp_data.get("code") == 100000:
                    return True
                if "已签" in str(resp_data):
                    return None
            except Exception as e:
                logger.debug(f"requests签到失败: {e}")

            logger.warning(f"超话 {containerid} 签到结果不确定: {result[:100] if result else 'empty'}")
            return False

        except Exception as e:
            logger.error(f"超话签到异常 ({containerid}): {e}")
            return False

    def get_topic_feed(self, containerid, scroll_times=2):
        """
        获取超话内的帖子列表。
        通过Selenium访问超话页面，解析DOM中的帖子。

        参数:
            containerid: 超话containerid
            scroll_times: 滚动次数
        返回: [{"mid": str, "text": str, "user_id": str, "user_name": str}, ...]
        """
        if not self.driver:
            logger.error("获取超话帖子需要Selenium driver")
            return []

        try:
            topic_url = f"https://weibo.com/p/{containerid}/super_index"
            self.driver.get(topic_url)
            time.sleep(4)

            # 滚动加载更多帖子
            for i in range(scroll_times):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(1.5, 3.0))

            page_source = self.driver.page_source
            return self._parse_topic_feed(page_source)

        except Exception as e:
            logger.error(f"获取超话帖子异常 ({containerid}): {e}")
            return []

    def _parse_topic_feed(self, html):
        """从超话页面HTML中解析帖子列表"""
        soup = BeautifulSoup(html, "html.parser")
        weibos = []

        # 超话页面使用老版微博架构，帖子在 div[mid][action-type='feed_list_item'] 中
        feed_items = soup.find_all("div", attrs={"action-type": "feed_list_item", "mid": True})

        for item in feed_items:
            mid = item.get("mid", "")
            if not mid:
                continue

            # 提取用户信息
            user_name = ""
            user_id = ""
            nick_el = item.find("a", class_="W_f14") or item.find("a", attrs={"nick-name": True})
            if nick_el:
                user_name = nick_el.get("nick-name", "") or nick_el.get("title", "") or nick_el.get_text(strip=True)
                usercard = nick_el.get("usercard", "")
                if "id=" in usercard:
                    user_id = usercard.split("id=")[1].split("&")[0]

            # 从tbinfo中提取uid
            if not user_id:
                tbinfo = item.get("tbinfo", "")
                if "ouid=" in tbinfo:
                    user_id = tbinfo.split("ouid=")[1].split("&")[0]

            # 提取微博正文
            text = ""
            text_el = item.find("div", class_="WB_text")
            if text_el:
                # 移除超话标签（#xxx[超话]# 或 xxx超话）
                text = text_el.get_text(strip=True)
                text = re.sub(r"#[^#]+\[超话\]#\s*", "", text)
                text = re.sub(r"^[^\s]{1,20}超话\s*", "", text)
                text = text.strip()

            # 判断是否为转发
            is_repost = bool(item.find("div", class_="WB_feed_expand"))

            if mid and text:
                weibos.append({
                    "mid": mid,
                    "text": text,
                    "user_id": user_id,
                    "user_name": user_name,
                    "is_repost": is_repost,
                })

        logger.info(f"超话页面解析到 {len(weibos)} 条帖子")
        return weibos

    def post_to_topic(self, containerid, content):
        """
        在超话中发帖。
        通过huati.weibo.com的发帖接口。

        参数:
            containerid: 超话containerid
            content: 发帖内容
        返回: True/False
        """
        if not self.driver:
            logger.error("超话发帖需要Selenium driver")
            return False

        try:
            # 先确保在超话页面上下文
            topic_url = f"https://weibo.com/p/{containerid}/super_index"
            current = self.driver.current_url
            if containerid not in current:
                self.driver.get(topic_url)
                time.sleep(3)

            # 获取CSRF token（xsrf-token）
            xsrf_token = ""
            cookies = self.driver.get_cookies()
            for c in cookies:
                if c["name"].upper() == "XSRF-TOKEN":
                    xsrf_token = c["value"]
                    break

            # 通过Selenium的fetch调用发帖API
            # 发帖内容需要包含超话标签
            send_url = f"{SEND_CONTENT_URL}?sign=super&page_id={containerid}"
            safe_content = content.replace("'", "\\'")
            script = (
                "try {"
                "    const formData = new URLSearchParams();"
                f"    formData.append('content', '{safe_content}');"
                f"    formData.append('page_id', '{containerid}');"
                f"    const resp = await fetch('{send_url}', {{"
                "        method: 'POST',"
                "        credentials: 'include',"
                "        headers: {"
                "            'Content-Type': 'application/x-www-form-urlencoded',"
                f"            'Referer': '{topic_url}'"
                "        },"
                "        body: formData.toString()"
                "    });"
                "    const text = await resp.text();"
                "    return text;"
                "} catch(e) {"
                "    return JSON.stringify({error: e.message});"
                "}"
            )
            result = self.driver.execute_script(script)

            if result:
                logger.debug(f"发帖响应: {result[:300]}")
                if '"code":100000' in result or '"ok":1' in result:
                    logger.info(f"超话发帖成功: {content[:50]}")
                    return True

            logger.warning(f"超话发帖可能失败: {result[:200] if result else 'empty'}")
            return False

        except Exception as e:
            logger.error(f"超话发帖异常: {e}")
            return False
