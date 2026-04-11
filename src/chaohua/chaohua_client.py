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

from src.scraper.parser import _extract_first_pic
from src.utils.logger import logger

# PC端Ajax接口
TOPIC_LIST_URL = "https://weibo.com/ajax/profile/topicContent"

# huati.weibo.cn 接口
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

        except ValueError as e:
            # JSON解析失败，打印实际响应内容帮助排查（可能是Cookie过期返回HTML）
            logger.error(f"获取超话列表JSON解析失败: {e}")
            logger.error(f"响应内容前200字符: {resp.text[:200]}")
            return []
        except Exception as e:
            logger.error(f"获取超话列表异常: {e}")
            return []

    def sign_in(self, containerid):
        """
        对单个超话执行签到。
        通过Selenium点击页面上的签到按钮实现。

        按钮结构:
            <a action-type="widget_take"
               action-data="api=...checkin&status=0&id=containerid">
                <span>签到</span>
            </a>
        status=0 未签到, status=1 已签到

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
            time.sleep(4)

            # 定位签到按钮: action-type="widget_take" 且 action-data 包含 checkin
            from selenium.webdriver.common.by import By
            buttons = self.driver.find_elements(
                By.CSS_SELECTOR, 'a[action-type="widget_take"]'
            )

            sign_btn = None
            for btn in buttons:
                action_data = btn.get_attribute("action-data") or ""
                if "checkin" in action_data:
                    sign_btn = btn
                    break

            if not sign_btn:
                logger.warning(f"超话 {containerid} 未找到签到按钮")
                return False

            # 检查 action-data 中的 status 字段
            action_data = sign_btn.get_attribute("action-data") or ""
            btn_text = sign_btn.text.strip()
            logger.info(f"签到按钮状态: text='{btn_text}', action-data='{action_data[:150]}'")

            if "status=1" in action_data:
                logger.info(f"超话 {containerid} 今日已签到（按钮status=1）")
                return None

            # 点击签到按钮（使用JS点击，避免被浮层遮挡）
            self.driver.execute_script("arguments[0].click();", sign_btn)
            time.sleep(3)

            # 验证签到结果：重新获取按钮状态
            buttons_after = self.driver.find_elements(
                By.CSS_SELECTOR, 'a[action-type="widget_take"]'
            )
            for btn in buttons_after:
                action_data_after = btn.get_attribute("action-data") or ""
                if "checkin" in action_data_after:
                    btn_text_after = btn.text.strip()
                    logger.info(f"签到后按钮状态: text='{btn_text_after}', action-data='{action_data_after[:150]}'")
                    if "status=1" in action_data_after or "已签到" in btn_text_after:
                        return True
                    break

            # 备选验证：检查页面是否出现签到成功提示
            page_source = self.driver.page_source
            if "签到成功" in page_source:
                return True

            logger.warning(f"超话 {containerid} 签到结果不确定")
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

            # 提取第一张图片URL（优先从媒体区域提取，复用parser的头像过滤逻辑）
            media_wrap = item.find("div", class_="WB_media_wrap")
            pic_url = _extract_first_pic(media_wrap) if media_wrap else ""

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

            # 取消"同步到微博"复选框（默认勾选）
            # checkbox结构: <label for="xxx"><input name="sync_wb" checked="checked">同步到微博</label>
            # 必须点击<label>才能正确触发取消
            try:
                sync_label = self.driver.find_element(
                    "xpath", "//label[contains(text(),'同步到微博')]"
                )
                sync_input = self.driver.find_element(
                    "css selector", "input[name='sync_wb']"
                )
                if sync_input.get_attribute("checked"):
                    sync_label.click()
                    time.sleep(0.3)
                    if not sync_input.get_attribute("checked"):
                        logger.info("已取消'同步到微博'勾选")
                    else:
                        logger.warning("点击label后checkbox仍为勾选状态")
            except Exception as e:
                logger.debug(f"取消同步勾选失败(非关键): {e}")

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
