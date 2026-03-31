"""
随机间隔任务调度器

基于APScheduler实现随机间隔的微博抓取和评论任务。
支持工作时段控制和每日评论上限检查。
"""

import random
import time
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.date import DateTrigger

from src.utils.config_loader import config
from src.utils.logger import logger
from src.storage.record_store import record_store


class TaskScheduler:
    """随机间隔任务调度器"""

    def __init__(self, task_func):
        """
        参数：
            task_func: 每次轮询要执行的任务函数（无参数）
        """
        self.scheduler = BlockingScheduler()
        self.task_func = task_func
        self._running = True

    def _is_work_hours(self):
        """检查当前是否在工作时段内"""
        hour = datetime.now().hour
        return config.work_hour_start <= hour < config.work_hour_end

    def _is_daily_limit_reached(self):
        """检查今日评论是否已达上限"""
        count = record_store.get_today_count()
        if count >= config.daily_limit:
            logger.info(f"今日评论数已达上限 ({count}/{config.daily_limit})，暂停评论")
            return True
        return False

    def _schedule_next(self):
        """安排下一次任务执行"""
        if not self._running:
            return

        delay = random.randint(config.poll_min, config.poll_max)
        next_time = datetime.fromtimestamp(time.time() + delay)
        logger.info(f"下一次轮询将在 {delay} 秒后 ({next_time.strftime('%H:%M:%S')}) 执行")

        self.scheduler.add_job(
            self._run_task,
            trigger=DateTrigger(run_date=next_time),
            id="next_poll",
            replace_existing=True,
        )

    def _run_task(self):
        """执行一次轮询任务"""
        if not self._is_work_hours():
            logger.info(f"当前不在工作时段 ({config.work_hour_start}:00-{config.work_hour_end}:00)，跳过本次轮询")
            self._schedule_next()
            return

        if self._is_daily_limit_reached():
            self._schedule_next()
            return

        try:
            logger.info("=" * 40)
            logger.info("开始执行轮询任务...")
            self.task_func()
            logger.info("轮询任务执行完成")
        except Exception as e:
            logger.error(f"轮询任务执行失败: {e}")
        finally:
            self._schedule_next()

    def start(self):
        """启动调度器"""
        logger.info("调度器启动，立即执行第一次任务...")
        # 立即执行第一次
        self.scheduler.add_job(
            self._run_task,
            trigger=DateTrigger(run_date=datetime.now()),
            id="first_poll",
        )
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("收到退出信号，调度器停止")
            self._running = False
            self.scheduler.shutdown(wait=False)

    def stop(self):
        """停止调度器"""
        self._running = False
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        logger.info("调度器已停止")
