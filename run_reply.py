"""
微博自动回复评论 — 回复模式

监控自己微博下收到的评论，自动生成并发送回复。
支持直接评论和楼中楼回复。
通过Selenium抓取评论收件箱页面获取评论。
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
from src.auth.login_manager import get_valid_cookies
from src.auth.oauth_manager import get_valid_token, get_uid
from src.scraper.weibo_scraper import WeiboScraper
from src.reply.reply_fetcher import fetch_comments_to_me
from src.reply.reply_generator import generate_reply
from src.reply.reply_sender import send_reply, send_reply_via_ui
from src.comment.publisher import RateLimitError
from src.storage.record_store import record_store
from src.scheduler.task_scheduler import TaskScheduler


class ReplyBot:
    """自动回复评论机器人"""

    RATE_LIMIT_COOLDOWN_MINUTES = 10

    def __init__(self):
        self.my_uid = None
        self.scraper = None
        self._rate_limit_until = None
        self._shutdown = False

    def init(self):
        """初始化：IP → Cookie → OAuth → Selenium"""
        logger.info("=" * 50)
        logger.info("微博自动回复评论 — 回复模式")
        logger.info("=" * 50)

        cookies = get_valid_cookies()
        if not cookies:
            logger.error("微博登录失败，程序退出")
            sys.exit(1)
        logger.info("Cookie验证通过 ✓")

        access_token = get_valid_token()
        if not access_token:
            logger.error("OAuth认证失败，程序退出")
            sys.exit(1)
        self.my_uid = str(get_uid(access_token))
        logger.info(f"OAuth认证通过 ✓ (UID: {self.my_uid})")

        # 启动Selenium浏览器
        self.scraper = WeiboScraper()
        self.scraper.start()
        logger.info("Selenium浏览器启动 ✓")

        logger.info("=" * 50)
        logger.info(f"  轮询间隔: {config.reply_poll_min}~{config.reply_poll_max}s")
        logger.info(f"  每日上限: {config.reply_daily_limit}")
        logger.info(f"  回复风格: {config.reply_prompt_name}")
        logger.info(f"  工作时段: {config.work_hour_start}:00-{config.work_hour_end}:00")
        logger.info("=" * 50)

    def poll_and_reply(self):
        """一次轮询：获取新评论 → 过滤 → 回复。返回建议等待秒数（None表示正常间隔）"""
        if self._rate_limit_until and datetime.now() < self._rate_limit_until:
            remaining = int((self._rate_limit_until - datetime.now()).total_seconds()) + 1
            logger.info(f"[回复] 频率限制冷却中，{self._rate_limit_until.strftime('%H:%M:%S')} 后恢复，跳过本次轮询")
            return remaining
        try:
            comments = fetch_comments_to_me(driver=self.scraper.driver)

            if not comments:
                return

            # 过滤
            reply_blacklist = config.reply_blacklist

            # 收集所有楼中楼回复的根评论ID，这些根评论不需要再回复
            # （有楼中楼说明根评论已经回复过了，只需回复最新的楼中楼）
            root_ids_from_sub_replies = set()
            for c in comments:
                root_id = c.get("root_comment_id")
                if root_id:
                    root_ids_from_sub_replies.add(root_id)

            new_comments = []
            for c in comments:
                # 跳过自己的评论
                if c["comment_user_id"] == self.my_uid:
                    continue
                # 跳过黑名单用户
                if c["comment_user_id"] in reply_blacklist:
                    continue
                # 跳过已回复的
                if record_store.is_replied(c["comment_id"]):
                    continue
                # 跳过空评论
                if not c["comment_text"].strip():
                    continue
                # 跳过已有楼中楼回复的根评论（只回复最新的楼中楼）
                if not c.get("root_comment_id") and c["comment_id"] in root_ids_from_sub_replies:
                    continue
                new_comments.append(c)

            if not new_comments:
                logger.info("没有需要回复的新评论")
                return

            logger.info(f"过滤后 {len(new_comments)} 条待回复")

            for c in new_comments:
                if record_store.get_reply_today_count() >= config.reply_daily_limit:
                    logger.info("已达今日回复上限")
                    break
                try:
                    self._reply_to_comment(c)
                except RateLimitError:
                    self._rate_limit_until = datetime.now() + timedelta(minutes=self.RATE_LIMIT_COOLDOWN_MINUTES)
                    logger.warning(f"[回复] 触发频率限制，冷却 {self.RATE_LIMIT_COOLDOWN_MINUTES} 分钟")
                    return self.RATE_LIMIT_COOLDOWN_MINUTES * 60
                except Exception as e:
                    logger.error(f"回复出错 (cid={c['comment_id']}): {e}")

        except Exception as e:
            logger.error(f"轮询异常: {e}")
            return False

    def _reply_to_comment(self, comment):
        """回复单条评论"""
        cid = comment["comment_id"]
        weibo_mid = comment["weibo_mid"]
        weibo_text = comment["weibo_text"]
        comment_text = comment["comment_text"]
        comment_user = comment["comment_user_name"]
        reply_comment_text = comment.get("reply_comment_text")
        root_comment_id = comment.get("root_comment_id")

        if root_comment_id:
            logger.info(f"回复楼中楼 @{comment_user} (cid={cid}, root={root_comment_id}): {comment_text[:60]}")
        else:
            logger.info(f"回复评论 @{comment_user} (cid={cid}): {comment_text[:60]}")

        # 生成回复
        reply_text = generate_reply(
            weibo_text=weibo_text,
            comment_text=comment_text,
            reply_comment_text=reply_comment_text,
        )
        if not reply_text:
            logger.warning(f"回复生成失败，跳过 cid={cid}")
            return

        # 随机延迟（支持优雅退出）
        delay = random.randint(config.reply_delay_min, config.reply_delay_max)
        logger.info(f"  等待 {delay}s → {reply_text}")
        for _ in range(delay):
            if self._shutdown:
                logger.info("收到退出信号，跳过发送")
                return
            time.sleep(1)

        # 发送回复（通过UI模拟方式，确保回复位置正确）
        result = send_reply_via_ui(
            self.scraper.driver,
            comment_user_name=comment_user,
            comment_text_snippet=comment_text[:30],
            reply_text=reply_text,
        )
        if result:
            record_store.add_reply_record(
                comment_id=cid,
                reply_text=reply_text,
                weibo_mid=weibo_mid,
                comment_user=comment_user,
                reply_cid=result.get("id"),
            )
            logger.info(f"  ✓ 回复成功")
        else:
            logger.warning(f"  ✗ 回复失败")

    def cleanup(self):
        self._shutdown = True
        if self.scraper:
            self.scraper.stop()
        logger.info("资源已清理")


def main():
    bot = ReplyBot()

    def signal_handler(sig, frame):
        logger.info("\n收到退出信号，正在清理...")
        bot.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        bot.init()
        scheduler = TaskScheduler(
            bot.poll_and_reply,
            poll_min=config.reply_poll_min,
            poll_max=config.reply_poll_max,
            check_daily_limit=False,
            service_name="回复",
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
