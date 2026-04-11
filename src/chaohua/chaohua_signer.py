"""
超话签到模块

遍历用户关注的超话，逐个执行签到。
使用PC Cookie方案，无需手机抓包。
"""

import random
import time
from datetime import datetime

from src.chaohua.chaohua_client import ChaohuaClient
from src.storage.record_store import record_store
from src.utils.config_loader import config
from src.utils.logger import logger
from src.utils.notifier import send_notification


class ChaohuaSigner:
    """超话签到器"""

    def __init__(self, client: ChaohuaClient):
        self.client = client
        self.sign_config = config.chaohua_sign_config

    def sign_all(self):
        """
        遍历关注的超话，逐个签到。
        返回: (成功数, 已签数, 失败数)
        """
        logger.info("=" * 40)
        logger.info("开始超话签到...")

        topics = self.client.get_followed_chaohua()
        if not topics:
            logger.info("未获取到关注的超话")
            return 0, 0, 0

        success_count = 0
        already_count = 0
        fail_count = 0
        delay_min = self.sign_config.get("delay_min", 5)
        delay_max = self.sign_config.get("delay_max", 10)

        for topic in topics:
            name = topic["name"]
            containerid = topic["containerid"]
            today = datetime.now().strftime("%Y-%m-%d")

            # 检查本地记录是否已签到
            if record_store.is_chaohua_signed(name, today):
                logger.info(f"  [{name}] 本地记录已签到，跳过")
                already_count += 1
                continue

            # 执行签到
            logger.info(f"  [{name}] 正在签到...")
            result = self.client.sign_in(containerid)

            if result is True:
                record_store.add_chaohua_sign_record(name, today)
                logger.info(f"  [{name}] 签到成功 ✓")
                success_count += 1
            elif result is None:
                # 已签到（接口返回已签）
                record_store.add_chaohua_sign_record(name, today)
                logger.info(f"  [{name}] 已签到，跳过")
                already_count += 1
            else:
                logger.warning(f"  [{name}] 签到失败")
                fail_count += 1

            # 随机延迟
            delay = random.uniform(delay_min, delay_max)
            time.sleep(delay)

        logger.info(f"超话签到完成: 成功{success_count}个, 已签{already_count}个, 失败{fail_count}个")

        if fail_count > 0:
            failed_names = [t["name"] for t in topics if not record_store.is_chaohua_signed(t["name"], datetime.now().strftime("%Y-%m-%d"))]
            send_notification(
                f"超话签到失败 {fail_count}个",
                f"失败超话: {', '.join(failed_names)}\n成功{success_count}个, 已签{already_count}个, 失败{fail_count}个"
            )

        return success_count, already_count, fail_count
