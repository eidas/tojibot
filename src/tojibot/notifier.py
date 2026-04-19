import smtplib
import ssl
from email.mime.text import MIMEText


class EmailNotifier:
    def __init__(self, gmail_address: str, app_password: str, notify_to: str) -> None:
        self._from = gmail_address
        self._password = app_password
        self._to = notify_to

    def send_error(self, subject: str, body: str) -> None:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = self._from
        msg["To"] = self._to

        context = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.login(self._from, self._password)
            smtp.sendmail(self._from, self._to, msg.as_string())
