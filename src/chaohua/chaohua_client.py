"""
微博超话API客户端

通过微博移动端内部API实现超话相关操作：
- 获取关注的超话列表
- 超话签到
- 获取超话feed
- 超话发帖

认证参数需通过手机抓包获取。
"""

import time
import random
from urllib.parse import urlparse, parse_qs

import requests

from src.utils.logger import logger

HEADERS = {
    "User-Agent": "Weibo/81434 (iPhone; iOS 17.0; Scale/3.00)",
    "Host": "api.weibo.cn",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

CARDLIST_URL = "https://api.weibo.cn/2/cardlist"
SIGN_URL = "https://api.weibo.cn/2/page/button"
STATUS_SEND_URL = "https://api.weibo.cn/2/statuses/send"


def parse_auth_params(auth_url):
    """从抓包URL中解析认证参数"""
    parsed = urlparse(auth_url)
    params = {}
    for k, v in parse_qs(parsed.query).items():
        params[k] = v[0] if len(v) == 1 else v
    return params


class ChaohuaClient:
    """微博超话API客户端"""

    def __init__(self, auth_url):
        """
        参数：
            auth_url: 从手机抓包获取的完整URL（包含gsid等认证参数）
        """
        self.auth_params = parse_auth_params(auth_url)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        logger.info(f"超话客户端初始化完成，认证参数: {list(self.auth_params.keys())}")

    def _request(self, url, extra_params=None, method="GET"):
        """发送带认证参数的请求"""
        params = dict(self.auth_params)
        if extra_params:
            params.update(extra_params)

        try:
            if method == "GET":
                resp = self.session.get(url, params=params, timeout=15)
            else:
                resp = self.session.post(url, data=params, timeout=15)

            data = resp.json()

            # 检查认证失败
            if data.get("errno") or data.get("error_code"):
                error_msg = data.get("errmsg") or data.get("error", "未知错误")
                error_code = data.get("errno") or data.get("error_code")
                logger.error(f"超话API错误 - 错误码: {error_code}, 信息: {error_msg}")
                if "login" in str(error_msg).lower() or error_code in (-100, 21327, 21332):
                    logger.error("认证参数已过期，请重新抓包获取auth_url")
                return None

            return data

        except requests.Timeout:
            logger.error(f"超话API请求超时: {url}")
            return None
        except requests.ConnectionError:
            logger.error(f"超话API网络连接失败: {url}")
            return None
        except Exception as e:
            logger.error(f"超话API请求异常: {e}")
            return None

    def get_followed_chaohua(self):
        """
        获取用户关注的所有超话列表（自动分页）。
        返回: [{"id": str, "name": str, "containerid": str, "is_signed": bool}, ...]
        """
        all_topics = []
        since_id = None

        while True:
            extra = {"containerid": "100803_-_followsuper"}
            if since_id:
                extra["since_id"] = since_id

            data = self._request(CARDLIST_URL, extra)
            if not data:
                break

            cards = data.get("cards", [])
            if not cards:
                break

            for card in cards:
                card_group = card.get("card_group", [])
                for item in card_group:
                    if item.get("card_type") == 8:
                        topic = {
                            "id": item.get("itemid", ""),
                            "name": item.get("title_sub", ""),
                            "containerid": item.get("scheme", "").split("containerid=")[-1].split("&")[0] if "containerid=" in item.get("scheme", "") else "",
                            "is_signed": "已签" in item.get("buttons", [{}])[0].get("name", "") if item.get("buttons") else False,
                        }
                        if topic["name"]:
                            all_topics.append(topic)

            # 获取下一页since_id
            cardlist_info = data.get("cardlistInfo", {})
            since_id = cardlist_info.get("since_id")
            if not since_id:
                break

            time.sleep(random.uniform(1, 2))

        logger.info(f"获取到 {len(all_topics)} 个关注超话")
        return all_topics

    def sign_in(self, request_url=None):
        """
        对单个超话执行签到。
        request_url: 签到按钮的request_url（从card中提取）
        返回: True/False
        """
        if not request_url:
            logger.warning("签到请求URL为空")
            return False

        # 签到URL可能是完整URL或相对路径
        if request_url.startswith("http"):
            # 从URL中提取额外参数
            parsed = urlparse(request_url)
            extra = {}
            for k, v in parse_qs(parsed.query).items():
                extra[k] = v[0]
        else:
            extra = {"request_url": request_url}

        data = self._request(SIGN_URL, extra)
        if data and data.get("result") == 1:
            return True
        if data and "已签到" in str(data):
            return True
        return False

    def get_chaohua_feed(self, containerid, since_id=None):
        """
        获取超话内的微博feed。
        返回: [{"mid": str, "text": str, "user_id": str, "user_name": str}, ...]
        """
        extra = {"containerid": containerid}
        if since_id:
            extra["since_id"] = since_id

        data = self._request(CARDLIST_URL, extra)
        if not data:
            return []

        weibos = []
        cards = data.get("cards", [])
        for card in cards:
            mblog = card.get("mblog")
            if not mblog:
                continue

            text = mblog.get("text", "")
            # 移除HTML标签
            import re
            text = re.sub(r"<[^>]+>", "", text).strip()
            if not text:
                continue

            user = mblog.get("user", {})
            weibos.append({
                "mid": str(mblog.get("mid", mblog.get("id", ""))),
                "text": text,
                "user_id": str(user.get("id", "")),
                "user_name": user.get("screen_name", ""),
                "is_repost": mblog.get("retweeted_status") is not None,
                "created_at": mblog.get("created_at", ""),
            })

        logger.info(f"超话feed获取到 {len(weibos)} 条微博")
        return weibos

    def post_to_chaohua(self, content, extparam=None):
        """
        在超话中发帖。
        content: 发帖内容
        extparam: 超话标识参数
        返回: True/False
        """
        extra = {
            "content": content,
        }
        if extparam:
            extra["extparam"] = extparam

        data = self._request(STATUS_SEND_URL, extra, method="POST")
        if data and data.get("id"):
            logger.info(f"超话发帖成功，微博ID: {data['id']}")
            return True
        else:
            logger.error(f"超话发帖失败: {data}")
            return False
