"""通过微博ID查询自己的评论并删除"""

import json
import sys
import io
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

import requests

from src.auth.oauth_manager import get_valid_token, get_uid

COMMENT_SHOW_URL = "https://api.weibo.com/2/comments/show.json"
COMMENT_DESTROY_URL = "https://api.weibo.com/2/comments/destroy.json"
RECORD_PATH = "data/commented_records.json"


def main():
    access_token = get_valid_token()
    if not access_token:
        print("OAuth认证失败")
        sys.exit(1)

    my_uid = get_uid(access_token)
    print(f"当前用户 UID: {my_uid}\n")

    # 读取本地记录
    with open(RECORD_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)

    commented = records.get("commented", {})
    if not commented:
        print("没有评论记录")
        return

    print(f"本地记录有 {len(commented)} 条评论，开始查找评论ID...\n")

    to_delete = []

    for mid, info in commented.items():
        comment_text = info.get("comment", "")
        user_name = info.get("user_name", "")

        # 查询该微博下的评论，找到自己的
        try:
            resp = requests.get(
                COMMENT_SHOW_URL,
                params={"access_token": access_token, "id": mid, "count": 50},
                timeout=15,
            )
            data = resp.json()
            comments = data.get("comments", [])

            for c in comments:
                cid = c.get("id")
                c_uid = str(c.get("user", {}).get("id", ""))
                c_text = c.get("text", "")

                if c_uid == str(my_uid):
                    to_delete.append((mid, cid, c_text[:40], user_name))
                    print(f"  找到: mid={mid} cid={cid} @{user_name}: {c_text[:40]}")

        except Exception as e:
            print(f"  查询 mid={mid} 失败: {e}")

        time.sleep(0.5)

    if not to_delete:
        print("\n没有找到可删除的评论")
        return

    print(f"\n共找到 {len(to_delete)} 条自己的评论，开始删除...\n")

    success = 0
    deleted_mids = []
    for mid, cid, text, user in to_delete:
        try:
            resp = requests.post(
                COMMENT_DESTROY_URL,
                data={"access_token": access_token, "cid": cid},
                timeout=15,
            )
            result = resp.json()
            if "id" in result:
                print(f"  ✓ 已删除 cid={cid} @{user}: {text}")
                success += 1
                deleted_mids.append(mid)
            else:
                error = result.get("error", "未知")
                print(f"  ✗ 删除失败 cid={cid}: {error}")
        except Exception as e:
            print(f"  ✗ 异常 cid={cid}: {e}")

        time.sleep(1)

    # 从记录中移除已删除的
    for mid in deleted_mids:
        commented.pop(mid, None)

    # 重置今日计数
    today_key = time.strftime("%Y-%m-%d")
    records["commented"] = commented
    if today_key in records.get("daily_counts", {}):
        remaining = max(0, records["daily_counts"][today_key] - success)
        records["daily_counts"][today_key] = remaining

    with open(RECORD_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"\n完成：成功删除 {success}/{len(to_delete)} 条，记录已更新")


if __name__ == "__main__":
    main()
