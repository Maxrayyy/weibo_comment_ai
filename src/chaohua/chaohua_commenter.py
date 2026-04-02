"""
超话评论模块

抓取超话帖子并自动生成AI评论。
使用PC Cookie方案 + OAuth评论API。
"""

import random
import time

from src.chaohua.chaohua_client import ChaohuaClient
from src.comment.ai_generator import generate_comment
from src.comment.publisher import publish_comment
from src.storage.record_store import record_store
from src.utils.config_loader import config
from src.utils.logger import logger


class ChaohuaCommenter:
    """超话评论器"""

    def __init__(self, client: ChaohuaClient, rip: str):
        self.client = client
        self.rip = rip
        self.comment_config = config.chaohua_comment_config

    def comment_on_topics(self):
        """
        遍历目标超话，抓取帖子并评论。
        返回: 成功评论数
        """
        if not self.comment_config.get("enabled"):
            return 0

        target_topics = self.comment_config.get("target_topics", [])
        if not target_topics:
            # 未配置则从关注的超话中获取
            all_topics = self.client.get_followed_chaohua()
            target_topics = [t["containerid"] for t in all_topics]

        if not target_topics:
            logger.info("没有可评论的超话")
            return 0

        daily_limit = self.comment_config.get("daily_limit", 20)
        total_success = 0

        for containerid in target_topics:
            if record_store.get_chaohua_comment_today_count() >= daily_limit:
                logger.info("超话评论已达今日上限")
                break

            logger.info(f"正在抓取超话 {containerid} 的帖子...")
            weibos = self.client.get_topic_feed(containerid)

            for weibo in weibos:
                if record_store.get_chaohua_comment_today_count() >= daily_limit:
                    break

                mid = weibo.get("mid", "")
                text = weibo.get("text", "")
                if not mid or not text:
                    continue

                if record_store.is_commented(mid):
                    continue

                if config.skip_repost and weibo.get("is_repost"):
                    continue

                comment = generate_comment(text, pic_url=weibo.get("pic_url"))
                if not comment:
                    continue

                delay = random.randint(config.comment_delay_min, config.comment_delay_max)
                logger.info(f"等待 {delay}s 后评论超话微博 {mid}...")
                time.sleep(delay)

                result = publish_comment(mid, comment, self.rip)
                if result:
                    record_store.add_record(mid, comment, weibo.get("user_name", ""), comment_id=result.get("id"))
                    record_store.increment_chaohua_comment_count()
                    total_success += 1
                    logger.info(f"超话评论成功 @{weibo.get('user_name', '?')}: {comment}")

            time.sleep(random.uniform(2, 5))

        logger.info(f"超话评论完成，共成功 {total_success} 条")
        return total_success
