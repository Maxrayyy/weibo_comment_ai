"""
已评论记录存储

持久化保存已评论的微博ID，避免重复评论。
记录每日评论计数。
"""

import json
import os
from datetime import datetime

from src.utils.logger import logger

RECORD_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "commented_records.json"
)


class RecordStore:
    """已评论记录管理"""

    def __init__(self):
        self._records = self._load()

    _DEFAULT_RECORDS = {
        "commented": {},
        "daily_counts": {},
        "chaohua_signed": {},
        "chaohua_posted": {},
        "chaohua_comment_counts": {},
        "chaohua_post_counts": {},
    }

    def _load(self):
        """从文件加载记录"""
        if not os.path.exists(RECORD_PATH):
            return dict(self._DEFAULT_RECORDS)
        try:
            with open(RECORD_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 确保所有key都存在（兼容旧数据）
            for key, default in self._DEFAULT_RECORDS.items():
                data.setdefault(key, default)
            logger.info(f"已加载 {len(data.get('commented', {}))} 条评论记录")
            return data
        except Exception as e:
            logger.error(f"加载评论记录失败: {e}")
            return dict(self._DEFAULT_RECORDS)

    def _save(self):
        """保存记录到文件"""
        os.makedirs(os.path.dirname(RECORD_PATH), exist_ok=True)
        with open(RECORD_PATH, "w", encoding="utf-8") as f:
            json.dump(self._records, f, ensure_ascii=False, indent=2)

    def is_commented(self, mid):
        """检查某条微博是否已评论"""
        return str(mid) in self._records["commented"]

    def add_record(self, mid, comment_text, user_name=""):
        """添加一条评论记录"""
        mid = str(mid)
        today = datetime.now().strftime("%Y-%m-%d")
        self._records["commented"][mid] = {
            "comment": comment_text,
            "user_name": user_name,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        # 更新每日计数
        self._records.setdefault("daily_counts", {})
        self._records["daily_counts"][today] = self._records["daily_counts"].get(today, 0) + 1
        self._save()
        logger.info(f"评论记录已保存，微博ID: {mid}")

    def get_today_count(self):
        """获取今日已评论数"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self._records.get("daily_counts", {}).get(today, 0)

    def get_total_count(self):
        """获取总评论数"""
        return len(self._records.get("commented", {}))

    # --- 超话签到记录 ---
    def is_chaohua_signed(self, topic_name, date=None):
        """检查某超话今日是否已签到"""
        date = date or datetime.now().strftime("%Y-%m-%d")
        signed = self._records.get("chaohua_signed", {}).get(date, [])
        return topic_name in signed

    def add_chaohua_sign_record(self, topic_name, date=None):
        """记录超话签到"""
        date = date or datetime.now().strftime("%Y-%m-%d")
        self._records.setdefault("chaohua_signed", {})
        self._records["chaohua_signed"].setdefault(date, [])
        if topic_name not in self._records["chaohua_signed"][date]:
            self._records["chaohua_signed"][date].append(topic_name)
        self._save()

    # --- 超话发帖记录 ---
    def add_chaohua_post_record(self, topic_id, content):
        """记录超话发帖"""
        today = datetime.now().strftime("%Y-%m-%d")
        self._records.setdefault("chaohua_post_counts", {})
        self._records["chaohua_post_counts"][today] = self._records["chaohua_post_counts"].get(today, 0) + 1
        self._save()

    def get_chaohua_post_today_count(self):
        """获取今日超话发帖数"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self._records.get("chaohua_post_counts", {}).get(today, 0)

    # --- 超话评论计数 ---
    def increment_chaohua_comment_count(self):
        """增加今日超话评论计数"""
        today = datetime.now().strftime("%Y-%m-%d")
        self._records.setdefault("chaohua_comment_counts", {})
        self._records["chaohua_comment_counts"][today] = self._records["chaohua_comment_counts"].get(today, 0) + 1
        self._save()

    def get_chaohua_comment_today_count(self):
        """获取今日超话评论数"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self._records.get("chaohua_comment_counts", {}).get(today, 0)


record_store = RecordStore()
