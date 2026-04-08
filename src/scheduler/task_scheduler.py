"""
多任务调度器

基于APScheduler实现随机间隔和定时任务调度。
支持工作时段控制和每日评论上限检查。
"""

import random
import time
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger

from src.utils.config_loader import config
from src.utils.logger import logger
from src.utils.notifier import send_notification
from src.storage.record_store import record_store


class TaskScheduler:
    """多任务调度器"""

    # 默认连续失败上限
    DEFAULT_MAX_CONSECUTIVE_FAILURES = 10

    def __init__(self, task_func, poll_min=None, poll_max=None,
                 check_work_hours=True, check_daily_limit=True,
                 max_consecutive_failures=None, service_name="unknown"):
        """
        参数：
            task_func: 每次轮询要执行的任务函数（无参数）
                       返回 False 表示系统性故障（如session失效），其他返回值视为正常
            poll_min/poll_max: 自定义主任务轮询间隔，None则使用config默认值
            check_work_hours: 是否检查工作时段，False则全天运行
            check_daily_limit: 是否检查每日评论上限，回复模式等自行管理上限的场景可关闭
            max_consecutive_failures: 连续失败N次后自动停止，None使用默认值
            service_name: 服务名称，用于告警通知
        """
        self.scheduler = BlockingScheduler()
        self.task_func = task_func
        self._running = True
        self._poll_min = poll_min
        self._poll_max = poll_max
        self._check_work_hours = check_work_hours
        self._check_daily_limit = check_daily_limit
        self._interval_tasks = {}  # name -> {func, poll_min, poll_max}
        self._consecutive_failures = 0
        self._max_consecutive_failures = (
            max_consecutive_failures or self.DEFAULT_MAX_CONSECUTIVE_FAILURES
        )
        self._service_name = service_name

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

    def _schedule_next(self, task_name="default", delay_override=None):
        """安排下一次任务执行。delay_override: 指定等待秒数（如频率限制冷却），跳过随机间隔"""
        if not self._running:
            return

        if delay_override and delay_override > 0:
            delay = delay_override
        elif task_name == "default":
            poll_min = self._poll_min or config.poll_min
            poll_max = self._poll_max or config.poll_max
            delay = random.randint(poll_min, poll_max)
        else:
            task_info = self._interval_tasks.get(task_name, {})
            poll_min = task_info.get("poll_min", config.poll_min)
            poll_max = task_info.get("poll_max", config.poll_max)
            delay = random.randint(poll_min, poll_max)

        next_time = datetime.fromtimestamp(time.time() + delay)
        logger.info(f"[{task_name}] 下一次轮询将在 {delay} 秒后 ({next_time.strftime('%H:%M:%S')}) 执行")

        self.scheduler.add_job(
            self._run_task if task_name == "default" else lambda: self._run_interval_task(task_name),
            trigger=DateTrigger(run_date=next_time),
            id=f"next_{task_name}",
            replace_existing=True,
        )

    def _run_task(self):
        """执行一次主轮询任务"""
        if self._check_work_hours and not self._is_work_hours():
            logger.info(f"当前不在工作时段 ({config.work_hour_start}:00-{config.work_hour_end}:00)，跳过本次轮询")
            self._schedule_next()
            return

        if self._check_daily_limit and self._is_daily_limit_reached():
            self._schedule_next()
            return

        suggested_delay = None
        try:
            logger.info("=" * 40)
            logger.info("开始执行轮询任务...")
            result = self.task_func()
            if result is False:
                # 任务函数明确报告系统性故障
                self._consecutive_failures += 1
                logger.warning(
                    f"任务报告系统性故障，连续失败 {self._consecutive_failures}/{self._max_consecutive_failures}"
                )
                if self._consecutive_failures >= self._max_consecutive_failures:
                    msg = f"[{self._service_name}] 连续失败已达 {self._max_consecutive_failures} 次，自动停止服务"
                    logger.error(msg)
                    send_notification(
                        f"微博Bot服务停止: {self._service_name}",
                        f"{msg}\n\n可能原因：Cookie过期或网络异常\n请刷新Cookie后重启服务",
                    )
                    self.stop()
                    return
            else:
                if self._consecutive_failures > 0:
                    logger.info(f"任务恢复正常，重置连续失败计数（之前连续失败{self._consecutive_failures}次）")
                self._consecutive_failures = 0
                suggested_delay = result
            logger.info("轮询任务执行完成")
        except Exception as e:
            self._consecutive_failures += 1
            logger.error(
                f"轮询任务执行失败: {e}（连续失败 {self._consecutive_failures}/{self._max_consecutive_failures}）"
            )
            if self._consecutive_failures >= self._max_consecutive_failures:
                msg = f"[{self._service_name}] 连续失败已达 {self._max_consecutive_failures} 次，自动停止服务"
                logger.error(msg)
                send_notification(
                    f"微博Bot服务停止: {self._service_name}",
                    f"{msg}\n\n异常信息：{e}\n请检查日志后重启服务",
                )
                self.stop()
                return
        finally:
            if self._running:
                self._schedule_next(delay_override=suggested_delay)

    def add_interval_task(self, name, func, poll_min, poll_max):
        """
        添加随机间隔轮询任务。
        name: 任务名称
        func: 任务函数（无参数）
        poll_min/poll_max: 轮询间隔范围（秒）
        """
        self._interval_tasks[name] = {
            "func": func,
            "poll_min": poll_min,
            "poll_max": poll_max,
        }

    def _run_interval_task(self, task_name):
        """执行一次间隔任务"""
        if self._check_work_hours and not self._is_work_hours():
            logger.info(f"[{task_name}] 当前不在工作时段，跳过")
            self._schedule_next(task_name)
            return

        task_info = self._interval_tasks.get(task_name)
        if not task_info:
            return

        try:
            logger.info("=" * 40)
            logger.info(f"[{task_name}] 开始执行...")
            task_info["func"]()
            logger.info(f"[{task_name}] 执行完成")
        except Exception as e:
            logger.error(f"[{task_name}] 执行失败: {e}")
        finally:
            self._schedule_next(task_name)

    def add_daily_task(self, name, func, schedule_time):
        """
        添加每日定时任务。
        name: 任务名称
        func: 任务函数
        schedule_time: "HH:MM" 格式
        """
        hour, minute = schedule_time.split(":")
        self.scheduler.add_job(
            func,
            trigger=CronTrigger(hour=int(hour), minute=int(minute)),
            id=f"daily_{name}",
            replace_existing=True,
        )
        logger.info(f"已注册每日定时任务 [{name}]，执行时间: {schedule_time}")

    def start(self):
        """启动调度器"""
        logger.info("调度器启动，立即执行主任务...")
        # 立即执行主任务
        self.scheduler.add_job(
            self._run_task,
            trigger=DateTrigger(run_date=datetime.now()),
            id="first_poll",
        )
        # 立即执行所有间隔任务的第一次
        for name in self._interval_tasks:
            next_time = datetime.fromtimestamp(time.time() + random.randint(5, 15))
            self.scheduler.add_job(
                lambda n=name: self._run_interval_task(n),
                trigger=DateTrigger(run_date=next_time),
                id=f"first_{name}",
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
