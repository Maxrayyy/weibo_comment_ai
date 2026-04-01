"""
超话发帖模块

在指定超话中自动发布内容。
使用PC Cookie方案。
"""

import random
import time

from src.chaohua.chaohua_client import ChaohuaClient
from src.storage.record_store import record_store
from src.utils.config_loader import config
from src.utils.logger import logger


class ChaohuaPoster:
    """超话发帖器"""

    def __init__(self, client: ChaohuaClient):
        self.client = client
        self.post_config = config.chaohua_post_config

    def post_to_topics(self):
        """
        向配置中的目标超话发帖。
        返回: 成功发帖数
        """
        if not self.post_config.get("enabled"):
            return 0

        target_topics = self.post_config.get("target_topics", [])
        if not target_topics:
            # 如果未配置目标超话，则向所有关注的超话发帖
            all_topics = self.client.get_followed_chaohua()
            target_topics = [t["containerid"] for t in all_topics]

        if not target_topics:
            logger.info("没有可发帖的超话")
            return 0

        daily_limit = self.post_config.get("daily_limit", 5)
        templates = self.post_config.get("templates", ["打卡"])
        success_count = 0

        for containerid in target_topics:
            if record_store.get_chaohua_post_today_count() >= daily_limit:
                logger.info("超话发帖已达今日上限")
                break

            content = random.choice(templates)
            logger.info(f"正在向超话 {containerid} 发帖: {content}")

            success = self.client.post_to_topic(containerid, content)
            if success:
                record_store.add_chaohua_post_record(containerid, content)
                success_count += 1

            time.sleep(random.uniform(3, 8))

        logger.info(f"超话发帖完成，成功 {success_count} 条")
        return success_count
