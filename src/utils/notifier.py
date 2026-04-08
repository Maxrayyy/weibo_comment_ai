"""
告警通知模块

支持两种通知渠道：
1. Server酱（微信推送）— 配置 notify.serverchan.send_key
2. 邮件（SMTP）— 配置 notify.email.*

配置示例（config.yaml）:
    notify:
      enabled: true
      serverchan:
        send_key: "SCT..."    # Server酱 SendKey，从 sct.ftqq.com 获取
      email:
        smtp_host: "smtp.qq.com"
        smtp_port: 465
        sender: "xxx@qq.com"
        password: "授权码"
        receiver: "xxx@qq.com"
"""

import requests

from src.utils.logger import logger
from src.utils.config_loader import config


def _get_notify_config():
    return config._config.get("notify", {})


def send_notification(title, content=""):
    """
    发送告警通知。优先Server酱，其次邮件。
    title: 通知标题
    content: 通知详情（可选）
    """
    cfg = _get_notify_config()
    if not cfg.get("enabled"):
        return

    sent = False

    # 尝试 Server酱
    sc_cfg = cfg.get("serverchan", {})
    send_key = sc_cfg.get("send_key")
    if send_key:
        sent = _send_serverchan(send_key, title, content)

    # 尝试邮件
    if not sent:
        email_cfg = cfg.get("email", {})
        if email_cfg.get("smtp_host"):
            sent = _send_email(email_cfg, title, content)

    if not sent:
        logger.warning(f"告警通知发送失败: {title}")


def _send_serverchan(send_key, title, content):
    """通过Server酱发送微信推送"""
    try:
        url = f"https://sctapi.ftqq.com/{send_key}.send"
        resp = requests.post(url, data={"title": title, "desp": content}, timeout=10)
        data = resp.json()
        if data.get("code") == 0:
            logger.info(f"Server酱通知发送成功: {title}")
            return True
        else:
            logger.warning(f"Server酱通知失败: {data}")
            return False
    except Exception as e:
        logger.warning(f"Server酱通知异常: {e}")
        return False


def _send_email(email_cfg, title, content):
    """通过SMTP发送邮件通知"""
    import smtplib
    from email.mime.text import MIMEText

    try:
        msg = MIMEText(content or title, "plain", "utf-8")
        msg["Subject"] = f"[微博Bot告警] {title}"
        msg["From"] = email_cfg["sender"]
        msg["To"] = email_cfg["receiver"]

        smtp_port = email_cfg.get("smtp_port", 465)
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(email_cfg["smtp_host"], smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(email_cfg["smtp_host"], smtp_port, timeout=10)
            server.starttls()

        server.login(email_cfg["sender"], email_cfg["password"])
        server.sendmail(email_cfg["sender"], email_cfg["receiver"], msg.as_string())
        server.quit()
        logger.info(f"邮件通知发送成功: {title}")
        return True
    except Exception as e:
        logger.warning(f"邮件通知异常: {e}")
        return False
