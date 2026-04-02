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

            # 提取第一张图片URL
            pic_url = ""
            media_wrap = item.find("div", class_="WB_media_wrap") or item
            img_el = media_wrap.find("img", src=re.compile(r"sinaimg\.cn"))
            if img_el:
                src = img_el.get("src", "")
                if "face" not in src and "emoticon" not in src:
                    pic_url = re.sub(
                        r"(sinaimg\.cn/)(thumbnail|bmiddle|orj360|orj480|thumb150|square|small|mw\d+|large)",
                        r"\1mw690",
                        src,
                    )
                    if pic_url.startswith("//"):
                        pic_url = "https:" + pic_url
                    elif pic_url.startswith("http://"):
                        pic_url = pic_url.replace("http://", "https://", 1)

            if mid and text:
                weibos.append({
                    "mid": mid,
                    "text": text,
                    "user_id": user_id,
                    "user_name": user_name,
                    "is_repost": is_repost,
                    "pic_url": pic_url,
                })

        logger.info(f"超话页面解析到 {len(weibos)} 条帖子")
        return weibos

    def _sync_cookies_from_driver(self):
        """从Selenium driver同步最新cookie到requests session"""
        if not self.driver:
            return
        for c in self.driver.get_cookies():
            self.session.cookies.set(
                c["name"], c["value"],
                domain=c.get("domain", ".weibo.com"),
                path=c.get("path", "/"),
            )

    def post_to_topic(self, containerid, content):
        """
        在超话中发帖。
        通过Selenium模拟用户操作：在发帖框输入内容并点击发送。

        参数:
            containerid: 超话containerid
            content: 发帖内容
        返回: True/False
        """
        if not self.driver:
            logger.error("超话发帖需要Selenium driver")
            return False

        try:
            topic_url = f"https://weibo.com/p/{containerid}/super_index"
            current = self.driver.current_url
            if containerid not in current:
                self.driver.get(topic_url)
                time.sleep(4)

            # 找到发帖输入框（placeholder: "掐指一算，此帖必火"）
            textarea = self.driver.find_element("css selector", "textarea.W_input")
            if not textarea:
                # 备选选择器
                textarea = self.driver.find_element("css selector", "textarea[placeholder*='必火']")

            # 点击textarea激活
            textarea.click()
            time.sleep(0.5)

            # 输入内容
            textarea.clear()
            textarea.send_keys(content)
            time.sleep(1)

            # 找到发送按钮并点击
            # 按钮是 a.W_btn_a，输入内容后会从 W_btn_a_disable 变为可点击
            submit_btn = self.driver.find_element(
                "css selector", "a.W_btn_a.btn_30px:not(.W_btn_a_disable)"
            )
            if not submit_btn:
                logger.warning("发送按钮仍为禁用状态，尝试强制点击")
                submit_btn = self.driver.find_element("css selector", "a.W_btn_a.btn_30px")

            submit_btn.click()
            time.sleep(3)

            # 检查是否发帖成功：textarea被清空或页面出现新帖子
            new_textarea_value = textarea.get_attribute("value") or ""
            if not new_textarea_value.strip():
                logger.info(f"超话发帖成功: {content[:50]}")
                return True

            # 检查页面是否有成功提示
            page_text = self.driver.page_source
            if "发布成功" in page_text:
                logger.info(f"超话发帖成功: {content[:50]}")
                return True

            logger.warning(f"超话发帖结果不确定，输入框内容: {new_textarea_value[:50]}")
            return False

        except Exception as e:
            logger.error(f"超话发帖异常: {e}")
            return False
