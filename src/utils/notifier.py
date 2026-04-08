"""
告警通知模块（邮件）

配置示例（config.yaml）:
    notify:
      enabled: true
      email:
        smtp_host: "smtp.163.com"
        smtp_port: 465
        sender: "xxx@163.com"
        password: "SMTP授权码"
        receiver: "xxx@163.com"
"""

from src.utils.logger import logger
from src.utils.config_loader import config


def _get_notify_config():
    return config._config.get("notify", {})


def send_notification(title, content=""):
    """
    发送邮件告警通知。
    title: 通知标题
    content: 通知详情（可选）
    """
    cfg = _get_notify_config()
    if not cfg.get("enabled"):
        return

    email_cfg = cfg.get("email", {})
    if not email_cfg.get("smtp_host"):
        logger.warning(f"告警通知未配置邮箱: {title}")
        return

    if not _send_email(email_cfg, title, content):
        logger.warning(f"告警通知发送失败: {title}")


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
