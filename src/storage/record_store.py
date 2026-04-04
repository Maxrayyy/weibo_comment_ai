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
        "replied": {},
        "reply_daily_counts": {},
        "reply_since_id": 0,
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
        """保存记录到文件（先合并磁盘上其他容器的变更，避免覆盖）"""
        os.makedirs(os.path.dirname(RECORD_PATH), exist_ok=True)
        # 读取磁盘最新数据并合并
        if os.path.exists(RECORD_PATH):
            try:
                with open(RECORD_PATH, "r", encoding="utf-8") as f:
                    disk_data = json.load(f)
                # 合并 dict 类型字段（commented, replied, daily_counts 等）
                for key in self._records:
                    if isinstance(self._records[key], dict) and isinstance(disk_data.get(key), dict):
                        merged = dict(disk_data[key])
                        merged.update(self._records[key])
                        self._records[key] = merged
                    elif isinstance(self._records[key], list) and isinstance(disk_data.get(key), list):
                        # 列表取并集（如 chaohua_signed）
                        for item in disk_data[key]:
                            if item not in self._records[key]:
                                self._records[key].append(item)
            except (json.JSONDecodeError, Exception):
                pass
        with open(RECORD_PATH, "w", encoding="utf-8") as f:
            json.dump(self._records, f, ensure_ascii=False, indent=2)

    def _reload(self):
        """从磁盘重新加载记录（获取其他容器的最新变更）"""
        self._records = self._load()

    def is_commented(self, mid):
        """检查某条微博是否已评论"""
        self._reload()
        return str(mid) in self._records["commented"]

    def add_record(self, mid, comment_text, user_name="", comment_id=None):
        """添加一条评论记录"""
        mid = str(mid)
        today = datetime.now().strftime("%Y-%m-%d")
        record = {
            "comment": comment_text,
            "user_name": user_name,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if comment_id:
            record["cid"] = str(comment_id)
        self._records["commented"][mid] = record
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


    # --- 回复评论记录 ---
    def is_replied(self, comment_id):
        """检查某条评论是否已回复"""
        self._reload()
        return str(comment_id) in self._records.get("replied", {})

    def add_reply_record(self, comment_id, reply_text, weibo_mid, comment_user, reply_cid=None):
        """添加一条回复记录"""
        comment_id = str(comment_id)
        today = datetime.now().strftime("%Y-%m-%d")
        record = {
            "reply_text": reply_text,
            "weibo_mid": str(weibo_mid),
            "comment_user": comment_user,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if reply_cid:
            record["reply_cid"] = str(reply_cid)
        self._records.setdefault("replied", {})[comment_id] = record
        self._records.setdefault("reply_daily_counts", {})
        self._records["reply_daily_counts"][today] = self._records["reply_daily_counts"].get(today, 0) + 1
        self._save()
        logger.info(f"回复记录已保存，评论ID: {comment_id}")

    def get_reply_today_count(self):
        """获取今日已回复数"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self._records.get("reply_daily_counts", {}).get(today, 0)

    def get_reply_since_id(self):
        """获取上次拉取的最大评论ID（用于增量拉取）"""
        return self._records.get("reply_since_id", 0)

    def set_reply_since_id(self, since_id):
        """更新增量拉取游标"""
        self._records["reply_since_id"] = since_id
        self._save()


record_store = RecordStore()
