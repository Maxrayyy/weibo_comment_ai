"""
微博全自动评论系统 — 主程序入口

整合所有模块，实现完整的自动评论工作流：
1. 加载配置 → 2. 登录验证 → 3. OAuth认证 → 4. 启动调度器
调度器循环：抓取新微博 → AI生成评论 → 随机延迟 → API发布评论
"""

import random
import signal
import sys
import time

from src.utils.logger import logger
from src.utils.config_loader import config
from src.auth.login_manager import get_valid_cookies
from src.auth.oauth_manager import get_valid_token, get_uid
from src.scraper.weibo_scraper import WeiboScraper
from src.comment.ai_generator import generate_comment
from src.comment.publisher import publish_comment
from src.storage.record_store import record_store
from src.scheduler.task_scheduler import TaskScheduler


class WeiboCommentBot:
    """微博自动评论机器人"""

    def __init__(self):
        self.scraper = None
        self.my_uid = None

    def init(self):
        """初始化：登录验证 + OAuth认证"""
        logger.info("=" * 50)
        logger.info("微博全自动评论系统启动")
        logger.info("=" * 50)

        # 1. Cookie登录验证
        logger.info("[1/3] 验证微博登录状态...")
        cookies = get_valid_cookies()
        if not cookies:
            logger.error("微博登录失败，程序退出")
            sys.exit(1)
        logger.info("微博登录验证通过 ✓")

        # 2. OAuth认证
        logger.info("[2/3] 获取OAuth access_token...")
        access_token = get_valid_token()
        if not access_token:
            logger.error("OAuth认证失败，程序退出")
            sys.exit(1)
        self.my_uid = get_uid(access_token)
        logger.info(f"OAuth认证通过 ✓ (UID: {self.my_uid})")

        # 3. 初始化抓取器
        logger.info("[3/3] 初始化微博抓取器...")
        self.scraper = WeiboScraper()
        self.scraper.start()
        logger.info("抓取器初始化完成 ✓")

        logger.info("=" * 50)
        logger.info("系统初始化完成，即将开始自动评论")
        logger.info(f"  模式: {config.strategy_mode}")
        logger.info(f"  每日上限: {config.daily_limit} 条")
        logger.info(f"  工作时段: {config.work_hour_start}:00 - {config.work_hour_end}:00")
        logger.info(f"  轮询间隔: {config.poll_min}~{config.poll_max} 秒")
        logger.info(f"  评论风格: {config.default_prompt_name}")
        logger.info("=" * 50)

    def poll_and_comment(self):
        """一次完整的轮询和评论流程"""
        try:
            # 1. 抓取新微博
            weibos = self._fetch_new_weibos()
            if not weibos:
                logger.info("本次轮询没有发现新微博")
                return

            logger.info(f"发现 {len(weibos)} 条新微博待评论")

            # 2. 逐条生成评论并发布
            for weibo in weibos:
                # 检查每日上限
                if record_store.get_today_count() >= config.daily_limit:
                    logger.info("已达今日评论上限，停止评论")
                    break

                try:
                    self._comment_on_weibo(weibo)
                except Exception as e:
                    logger.error(f"评论单条微博时出错 (mid={weibo.get('mid', '?')}): {e}")
                    continue

        except Exception as e:
            logger.error(f"轮询任务执行异常: {e}")
            # 尝试重启抓取器
            try:
                logger.info("尝试重启抓取器...")
                if self.scraper:
                    self.scraper.stop()
                self.scraper = WeiboScraper()
                self.scraper.start()
                logger.info("抓取器重启成功")
            except Exception as restart_err:
                logger.error(f"抓取器重启失败: {restart_err}")

    def _fetch_new_weibos(self):
        """抓取并筛选新微博"""
        all_weibos = []

        if config.strategy_mode == "whitelist" and config.whitelist:
            # 白名单模式：逐个抓取白名单用户的微博
            for uid in config.whitelist:
                weibos = self.scraper.fetch_user_weibos(uid)
                all_weibos.extend(weibos)
        else:
            # 黑名单模式或无白名单：抓取首页时间线
            all_weibos = self.scraper.fetch_home_timeline()

        # 过滤
        new_weibos = []
        for weibo in all_weibos:
            mid = weibo.get("mid", "")
            if not mid:
                continue
            # 跳过已评论的
            if record_store.is_commented(mid):
                continue
            # 黑名单过滤
            if config.strategy_mode == "blacklist" and weibo.get("user_id") in [str(u) for u in config.blacklist]:
                continue
            # 跳过转发微博（如果配置了）
            if config.skip_repost and weibo.get("is_repost"):
                continue
            # 跳过内容为空的
            if not weibo.get("text", "").strip():
                continue
            new_weibos.append(weibo)

        return new_weibos

    def _comment_on_weibo(self, weibo):
        """对一条微博生成评论并发布"""
        mid = weibo["mid"]
        text = weibo["text"]
        user_name = weibo.get("user_name", "未知用户")

        logger.info(f"正在评论 @{user_name} 的微博 (ID: {mid})")
        logger.info(f"  微博内容: {text[:80]}{'...' if len(text) > 80 else ''}")

        # 生成评论
        comment = generate_comment(text)
        if not comment:
            logger.warning(f"评论生成失败，跳过微博 {mid}")
            return

        # 随机延迟，模拟真人
        delay = random.randint(config.comment_delay_min, config.comment_delay_max)
        logger.info(f"  等待 {delay} 秒后发布评论...")
        time.sleep(delay)

        # 发布评论
        result = publish_comment(mid, comment)
        if result:
            record_store.add_record(mid, comment, user_name)
            logger.info(f"  ✓ 评论成功: {comment}")
        else:
            logger.warning(f"  ✗ 评论发布失败")

    def cleanup(self):
        """清理资源"""
        if self.scraper:
            self.scraper.stop()
        logger.info("资源已清理")


def main():
    bot = WeiboCommentBot()

    # 优雅退出
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
