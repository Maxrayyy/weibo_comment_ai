"""
微博自动评论 — 时间线模式（API抓取）

通过微博官方API抓取首页时间线，过滤目标用户微博后自动评论。
"""

import random
import signal
import sys
import time

from dotenv import load_dotenv
load_dotenv()

import os
os.environ["WDM_LOCAL"] = "1"
os.environ["WDM_SSL_VERIFY"] = "0"

from src.utils.logger import logger
from src.utils.config_loader import config
from src.utils.rip_provider import get_rip
from src.auth.login_manager import get_valid_cookies
from src.auth.oauth_manager import get_valid_token, get_uid
from src.scraper.api_fetcher import fetch_friends_weibos, fetch_followers
from src.comment.ai_generator import generate_comment
from src.comment.publisher import publish_comment
from src.storage.record_store import record_store
from src.scheduler.task_scheduler import TaskScheduler


class TimelineBot:
    """时间线自动评论机器人（API模式）"""

    def __init__(self):
        self.my_uid = None
        self.target_uids = []
        self.rip = None

    def init(self):
        """初始化：IP → Cookie → OAuth → 目标用户"""
        logger.info("=" * 50)
        logger.info("微博自动评论 — 时间线模式")
        logger.info("=" * 50)

        self.rip = get_rip()
        if not self.rip:
            logger.error("无法获取公网IP，程序退出")
            sys.exit(1)
        logger.info(f"公网IP: {self.rip}")

        cookies = get_valid_cookies()
        if not cookies:
            logger.error("微博登录失败，程序退出")
            sys.exit(1)
        logger.info("Cookie验证通过 ✓")

        access_token = get_valid_token()
        if not access_token:
            logger.error("OAuth认证失败，程序退出")
            sys.exit(1)
        self.my_uid = get_uid(access_token)
        logger.info(f"OAuth认证通过 ✓ (UID: {self.my_uid})")

        if config.whitelist:
            self.target_uids = [str(uid) for uid in config.whitelist]
            logger.info(f"白名单模式，{len(self.target_uids)} 个目标用户")
        else:
            followers = fetch_followers(self.my_uid)
            self.target_uids = [f["uid"] for f in followers]
            logger.info(f"从粉丝列表获取 {len(self.target_uids)} 个目标用户")

        logger.info("=" * 50)
        logger.info(f"  轮询间隔: {config.poll_min}~{config.poll_max}s")
        logger.info(f"  每日上限: {config.daily_limit} | 风格: {config.default_prompt_name}")
        logger.info(f"  工作时段: {config.work_hour_start}:00-{config.work_hour_end}:00")
        logger.info("=" * 50)

    def poll_and_comment(self):
        """一次轮询：API抓取 → 过滤 → 评论"""
        try:
            all_weibos = fetch_friends_weibos(count=70, page=2)
            logger.info(f"API抓取到 {len(all_weibos)} 条微博")

            new_weibos = []
            for weibo in all_weibos:
                mid = weibo.get("mid", "")
                if not mid or not weibo.get("text", "").strip():
                    continue
                if self.target_uids and weibo.get("user_id") not in self.target_uids:
                    continue
                if weibo.get("user_id") == self.my_uid:
                    continue
                if record_store.is_commented(mid):
                    continue
                if config.skip_repost and weibo.get("is_repost"):
                    continue
                new_weibos.append(weibo)

            if not new_weibos:
                logger.info("没有新微博")
                return

            logger.info(f"过滤后 {len(new_weibos)} 条待评论")

            for weibo in new_weibos:
                if record_store.get_today_count() >= config.daily_limit:
                    logger.info("已达今日上限")
                    break
                try:
                    self._comment_on_weibo(weibo)
                except Exception as e:
                    logger.error(f"评论出错 (mid={weibo.get('mid', '?')}): {e}")

        except Exception as e:
            logger.error(f"轮询异常: {e}")

    def _comment_on_weibo(self, weibo):
        mid = weibo["mid"]
        text = weibo["text"]
        user_name = weibo.get("user_name", "未知用户")

        logger.info(f"评论 @{user_name} (mid={mid}): {text[:80]}")

        comment = generate_comment(text)
        if not comment:
            logger.warning(f"评论生成失败，跳过 {mid}")
            return

        delay = random.randint(config.comment_delay_min, config.comment_delay_max)
        logger.info(f"  等待 {delay}s → {comment}")
        time.sleep(delay)

        result = publish_comment(mid, comment, self.rip)
        if result:
            record_store.add_record(mid, comment, user_name, comment_id=result.get("id"))
            logger.info(f"  ✓ 评论成功")
        else:
            logger.warning(f"  ✗ 评论失败")

    def cleanup(self):
        logger.info("资源已清理")


def main():
    bot = TimelineBot()

    def signal_handler(sig, frame):
        logger.info("\n收到退出信号，正在清理...")
        bot.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        bot.init()
        scheduler = TaskScheduler(bot.poll_and_comment)
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("用户手动退出")
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
    finally:
        bot.cleanup()


if __name__ == "__main__":
    main()
