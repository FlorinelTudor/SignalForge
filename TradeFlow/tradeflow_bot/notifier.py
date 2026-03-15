from __future__ import annotations

import json
import smtplib
from email.message import EmailMessage
from pathlib import Path

import requests

from tradeflow_bot.config import Settings


class Notifier:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.log_file = settings.log_dir / "notifications.log"

    def send(self, subject: str, body: str) -> None:
        line = f"{subject}: {body}"
        self._append_log(line)

        if self.settings.webhook_url:
            self._send_webhook(subject=subject, body=body)
        if self.settings.notify_email_to and self.settings.smtp_host and self.settings.smtp_user:
            self._send_email(subject=subject, body=body)

    def _send_webhook(self, subject: str, body: str) -> None:
        payload = {"text": f"{subject}\n{body}"}
        try:
            requests.post(self.settings.webhook_url, data=json.dumps(payload), timeout=10)
        except Exception as exc:
            self._append_log(f"webhook_error: {exc}")

    def _send_email(self, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.settings.smtp_user
        msg["To"] = self.settings.notify_email_to
        msg.set_content(body)

        try:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=15) as smtp:
                smtp.starttls()
                smtp.login(self.settings.smtp_user, self.settings.smtp_password)
                smtp.send_message(msg)
        except Exception as exc:
            self._append_log(f"email_error: {exc}")

    def _append_log(self, line: str) -> None:
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
