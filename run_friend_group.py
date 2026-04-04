"""
微博自动评论 — 好友圈模式（Selenium抓取）

通过Selenium抓取好友圈分组页面微博，自动生成AI评论并发布。
独立于时间线模式，可单独运行。
"""

import random
import signal
import sys
import time
from datetime import datetime, timedelta

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
from src.scraper.weibo_scraper import WeiboScraper
from src.comment.ai_generator import generate_comment
from src.comment.publisher import publish_comment, RateLimitError
from src.storage.record_store import record_store
from src.scheduler.task_scheduler import TaskScheduler


class FriendGroupBot:
    """好友圈自动评论机器人（Selenium模式）"""

    # 频率限制冷却时间（分钟）
    RATE_LIMIT_COOLDOWN_MINUTES = 10

    def __init__(self):
        self.my_uid = None
        self.rip = None
        self.scraper = None
        self._rate_limit_until = None

    def init(self):
        """初始化：IP → Cookie → OAuth → Selenium浏览器"""
        logger.info("=" * 50)
        logger.info("微博自动评论 — 好友圈模式")
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

        # 启动Selenium浏览器
        self.scraper = WeiboScraper()
        self.scraper.start()
        logger.info("Selenium浏览器启动 ✓")

        gid = config.friend_group_gid
        logger.info("=" * 50)
        logger.info(f"  好友圈GID: {gid}")
        logger.info(f"  轮询间隔: {config.friend_group_poll_min}~{config.friend_group_poll_max}s")
        logger.info(f"  滚动次数: {config.friend_group_scroll_times}")
        logger.info(f"  每日上限: {config.daily_limit} | 风格: {config.default_prompt_name}")
        logger.info(f"  工作时段: 全天运行（无时间限制）")
        logger.info("=" * 50)

    def poll_and_comment(self):
        """一次轮询：Selenium抓取好友圈 → 过滤 → 评论"""
        # 频率限制冷却检查
        if self._rate_limit_until and datetime.now() < self._rate_limit_until:
            logger.info(f"[好友圈] 频率限制冷却中，{self._rate_limit_until.strftime('%H:%M:%S')} 后恢复")
            return
        try:
            gid = config.friend_group_gid
            scroll_times = config.friend_group_scroll_times
            weibos = self.scraper.fetch_group_timeline(gid, scroll_times)

            if not weibos:
                logger.info("[好友圈] 没有新微博")
                return

            # 过滤
            new_weibos = []
            for weibo in weibos:
                mid = weibo.get("mid", "")
                if not mid or not weibo.get("text", "").strip():
                    continue
                if weibo.get("user_id") == self.my_uid:
                    continue
                if record_store.is_commented(mid):
                    continue
                if config.skip_repost and weibo.get("is_repost"):
                    continue
                new_weibos.append(weibo)

            if not new_weibos:
                logger.info("[好友圈] 过滤后无新微博")
                return

            logger.info(f"[好友圈] {len(new_weibos)} 条待评论")

            for weibo in new_weibos:
                if record_store.get_today_count() >= config.daily_limit:
                    logger.info("[好友圈] 已达今日上限")
                    break
                try:
                    self._comment_on_weibo(weibo)
                except RateLimitError:
                    self._rate_limit_until = datetime.now() + timedelta(minutes=self.RATE_LIMIT_COOLDOWN_MINUTES)
                    logger.warning(f"[好友圈] 触发频率限制，冷却 {self.RATE_LIMIT_COOLDOWN_MINUTES} 分钟")
                    break
                except Exception as e:
                    logger.error(f"[好友圈] 评论出错 (mid={weibo.get('mid', '?')}): {e}")

        except Exception as e:
            logger.error(f"[好友圈] 轮询异常: {e}")

    def _comment_on_weibo(self, weibo):
        mid = weibo["mid"]
        text = weibo["text"]
        user_name = weibo.get("user_name", "未知用户")

        logger.info(f"评论 @{user_name} (mid={mid}): {text[:80]}")

        comment = generate_comment(text, pic_url=weibo.get("pic_url"))
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
        if self.scraper:
            self.scraper.stop()
        logger.info("资源已清理")


def main():
    bot = FriendGroupBot()

    def signal_handler(sig, frame):
        logger.info("\n收到退出信号，正在清理...")
        bot.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        bot.init()
        scheduler = TaskScheduler(
            bot.poll_and_comment,
            poll_min=config.friend_group_poll_min,
            poll_max=config.friend_group_poll_max,
            check_work_hours=False,
        )
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("用户手动退出")
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
    finally:
        bot.cleanup()


if __name__ == "__main__":
    main()
