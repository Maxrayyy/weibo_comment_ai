"""
微博自动超话 — 签到/发帖/评论

基于PC Cookie，通过Selenium + Ajax API实现：
- 每日自动签到所有关注的超话
- 定时向指定超话发帖
- 轮询超话帖子并自动AI评论

独立于时间线模式和好友圈模式，可单独运行。
"""

import signal
import sys

from dotenv import load_dotenv
load_dotenv()

import os
os.environ["WDM_LOCAL"] = "1"
os.environ["WDM_SSL_VERIFY"] = "0"

from src.utils.logger import logger
from src.utils.config_loader import config
from src.utils.rip_provider import get_rip
from src.auth.login_manager import get_valid_cookies, load_cookies
from src.auth.oauth_manager import get_valid_token, get_uid
from src.scraper.weibo_scraper import WeiboScraper
from src.chaohua.chaohua_client import ChaohuaClient
from src.chaohua.chaohua_signer import ChaohuaSigner
from src.chaohua.chaohua_poster import ChaohuaPoster
from src.chaohua.chaohua_commenter import ChaohuaCommenter
from src.scheduler.task_scheduler import TaskScheduler


class ChaohuaBot:
    """超话自动机器人（PC Cookie方案）"""

    def __init__(self):
        self.my_uid = None
        self.rip = None
        self.scraper = None
        self.client = None
        self.signer = None
        self.poster = None
        self.commenter = None

    def init(self):
        """初始化：IP → Cookie → OAuth → Selenium → 超话客户端"""
        logger.info("=" * 50)
        logger.info("微博自动超话 — PC Cookie方案")
        logger.info("=" * 50)

        # 公网IP
        self.rip = get_rip()
        if not self.rip:
            logger.error("无法获取公网IP，程序退出")
            sys.exit(1)
        logger.info(f"公网IP: {self.rip}")

        # Cookie验证
        cookies = get_valid_cookies()
        if not cookies:
            logger.error("微博登录失败，程序退出")
            sys.exit(1)
        logger.info("Cookie验证通过 ✓")

        # OAuth
        access_token = get_valid_token()
        if not access_token:
            logger.error("OAuth认证失败，程序退出")
            sys.exit(1)
        self.my_uid = get_uid(access_token)
        logger.info(f"OAuth认证通过 ✓ (UID: {self.my_uid})")

        # Selenium浏览器
        self.scraper = WeiboScraper()
        self.scraper.start()
        logger.info("Selenium浏览器启动 ✓")

        # 超话客户端
        raw_cookies = load_cookies()
        self.client = ChaohuaClient(
            uid=self.my_uid,
            cookies=raw_cookies,
            driver=self.scraper.driver,
        )

        # 初始化各功能模块
        self.signer = ChaohuaSigner(self.client)
        self.poster = ChaohuaPoster(self.client)
        self.commenter = ChaohuaCommenter(self.client, self.rip)

        # 打印配置
        sign_cfg = config.chaohua_sign_config
        post_cfg = config.chaohua_post_config
        comment_cfg = config.chaohua_comment_config
        logger.info("=" * 50)
        logger.info(f"  签到: {'开启' if sign_cfg.get('enabled') else '关闭'}"
                     f" (每日 {sign_cfg.get('schedule', '08:00')})")
        logger.info(f"  发帖: {'开启' if post_cfg.get('enabled') else '关闭'}"
                     f" (上限 {post_cfg.get('daily_limit', 5)}/天)")
        logger.info(f"  评论: {'开启' if comment_cfg.get('enabled') else '关闭'}"
                     f" (上限 {comment_cfg.get('daily_limit', 20)}/天)")
        logger.info(f"  工作时段: {config.work_hour_start}:00-{config.work_hour_end}:00")
        logger.info("=" * 50)

    def do_sign(self):
        """执行签到任务"""
        try:
            self.signer.sign_all()
        except Exception as e:
            logger.error(f"签到任务异常: {e}")

    def do_comment(self):
        """执行评论任务"""
        try:
            self.commenter.comment_on_topics()
        except Exception as e:
            logger.error(f"评论任务异常: {e}")

    def do_post(self):
        """执行发帖任务"""
        try:
            self.poster.post_to_topics()
        except Exception as e:
            logger.error(f"发帖任务异常: {e}")

    def cleanup(self):
        if self.scraper:
            self.scraper.stop()
        logger.info("资源已清理")


def main():
    bot = ChaohuaBot()

    def signal_handler(sig, frame):
        logger.info("\n收到退出信号，正在清理...")
        bot.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        bot.init()

        sign_cfg = config.chaohua_sign_config
        comment_cfg = config.chaohua_comment_config

        # 主任务：评论轮询（如果开启）
        if comment_cfg.get("enabled"):
            scheduler = TaskScheduler(
                bot.do_comment,
                poll_min=comment_cfg.get("poll_min", 120),
                poll_max=comment_cfg.get("poll_max", 300),
            )
        else:
            # 没有评论任务时，用签到作为主任务（只执行一次后等待）
            scheduler = TaskScheduler(
                bot.do_sign,
                poll_min=3600,
                poll_max=7200,
            )

        # 添加每日签到定时任务
        if sign_cfg.get("enabled"):
            schedule_time = sign_cfg.get("schedule", "08:00")
            scheduler.add_daily_task("chaohua_sign", bot.do_sign, schedule_time)
            # 启动时也立即签到一次
            bot.do_sign()

        scheduler.start()

    except KeyboardInterrupt:
        logger.info("用户手动退出")
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
    finally:
        bot.cleanup()


if __name__ == "__main__":
    main()
