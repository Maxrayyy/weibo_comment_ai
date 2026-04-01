"""
批量删除评论工具

从评论记录或API查询中获取评论ID，逐个删除。
用法：
    python delete_comments.py              # 删除记录中所有有cid的评论
    python delete_comments.py --all        # 先从API查自己的评论，再全部删除
    python delete_comments.py --mid 123    # 删除指定微博下自己的评论
"""

import argparse
import json
import sys
import io
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

import requests

from src.auth.oauth_manager import get_valid_token, get_uid
from src.utils.logger import logger

COMMENT_DESTROY_URL = "https://api.weibo.com/2/comments/destroy.json"
MY_COMMENTS_URL = "https://api.weibo.com/2/comments/by_me.json"
RECORD_PATH = "data/commented_records.json"


def delete_comment(cid, access_token):
    """删除单条评论"""
    try:
        resp = requests.post(
            COMMENT_DESTROY_URL,
            data={"access_token": access_token, "cid": cid},
            timeout=15,
        )
        result = resp.json()
        if "id" in result:
            return True
        else:
            error = result.get("error", "未知错误")
            error_code = result.get("error_code", "")
            logger.warning(f"删除评论 {cid} 失败: [{error_code}] {error}")
            return False
    except Exception as e:
        logger.error(f"删除评论 {cid} 异常: {e}")
        return False


def fetch_my_comments(access_token, count=50, page=1):
    """获取自己发出的评论列表"""
    try:
        resp = requests.get(
            MY_COMMENTS_URL,
            params={"access_token": access_token, "count": count, "page": page},
            timeout=15,
        )
        data = resp.json()
        return data.get("comments", [])
    except Exception as e:
        logger.error(f"获取评论列表失败: {e}")
        return []


def delete_from_records(access_token):
    """从本地记录中删除所有有cid的评论"""
    try:
        with open(RECORD_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)
    except FileNotFoundError:
        print("未找到评论记录文件")
        return

    commented = records.get("commented", {})
    cids = []
    for mid, info in commented.items():
        cid = info.get("cid")
        if cid:
            cids.append((mid, cid, info.get("comment", "")[:30], info.get("user_name", "")))

    if not cids:
        print("记录中没有可删除的评论（缺少cid）。使用 --all 从API获取并删除。")
        return

    print(f"找到 {len(cids)} 条可删除的评论：")
    for mid, cid, text, user in cids:
        print(f"  mid={mid} cid={cid} @{user}: {text}")

    confirm = input(f"\n确认删除以上 {len(cids)} 条评论？(y/N): ").strip().lower()
    if confirm != "y":
        print("已取消")
        return

    success = 0
    for mid, cid, text, user in cids:
        if delete_comment(cid, access_token):
            print(f"  ✓ 已删除 cid={cid} @{user}: {text}")
            # 从记录中移除
            commented.pop(mid, None)
            success += 1
        else:
            print(f"  ✗ 删除失败 cid={cid}")
        time.sleep(1)

    # 更新记录文件
    records["commented"] = commented
    with open(RECORD_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"\n完成：成功删除 {success}/{len(cids)} 条评论")


def delete_all_from_api(access_token):
    """从API获取所有自己的评论，逐个删除"""
    all_comments = []
    for page in range(1, 11):  # 最多查10页
        comments = fetch_my_comments(access_token, count=50, page=page)
        if not comments:
            break
        all_comments.extend(comments)
        time.sleep(0.5)

    if not all_comments:
        print("没有找到任何评论")
        return

    print(f"从API获取到 {len(all_comments)} 条评论：")
    for c in all_comments:
        cid = c.get("id", "")
        text = c.get("text", "")[:40]
        status = c.get("status", {})
        mid = status.get("mid", status.get("id", ""))
        user = status.get("user", {}).get("screen_name", "?")
        print(f"  cid={cid} @{user} mid={mid}: {text}")

    confirm = input(f"\n确认删除以上 {len(all_comments)} 条评论？(y/N): ").strip().lower()
    if confirm != "y":
        print("已取消")
        return

    success = 0
    for c in all_comments:
        cid = c.get("id", "")
        if not cid:
            continue
        text = c.get("text", "")[:30]
        if delete_comment(cid, access_token):
            print(f"  ✓ 已删除 cid={cid}: {text}")
            success += 1
        else:
            print(f"  ✗ 删除失败 cid={cid}")
        time.sleep(1)

    # 清空本地记录
    try:
        with open(RECORD_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)
        records["commented"] = {}
        with open(RECORD_PATH, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        print("本地评论记录已清空")
    except Exception:
        pass

    print(f"\n完成：成功删除 {success}/{len(all_comments)} 条评论")


def main():
    parser = argparse.ArgumentParser(description="批量删除微博评论")
    parser.add_argument("--all", action="store_true", help="从API查询所有自己的评论并删除")
    parser.add_argument("--mid", type=str, help="删除指定微博下的自己的评论")
    args = parser.parse_args()

    access_token = get_valid_token()
    if not access_token:
        print("OAuth认证失败")
        sys.exit(1)

    uid = get_uid(access_token)
    print(f"当前用户 UID: {uid}\n")

    if args.all:
        delete_all_from_api(access_token)
    else:
        delete_from_records(access_token)


if __name__ == "__main__":
    main()
