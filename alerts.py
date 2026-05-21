from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def send_absent_alert(student: dict, target_date: str) -> dict:
    message = (
        f"Attendance alert: {student['name']} ({student['roll_no']}) "
        f"was marked absent on {target_date}."
    )
    sent_any = False
    reasons = []

    email_result = _send_email(student.get("email"), message)
    sms_result = _send_sms(student.get("phone"), message)

    sent_any = email_result["sent"] or sms_result["sent"]
    if not email_result["sent"]:
        reasons.append(f"email: {email_result['reason']}")
    if not sms_result["sent"]:
        reasons.append(f"sms: {sms_result['reason']}")

    return {"sent": sent_any, "reason": "; ".join(reasons) if reasons else "sent"}


def _send_email(recipient: str | None, body: str) -> dict:
    if not recipient:
        return {"sent": False, "reason": "no recipient email"}

    host = os.getenv("SMTP_HOST")
    sender = os.getenv("SMTP_FROM") or os.getenv("SMTP_USERNAME")
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    port = int(os.getenv("SMTP_PORT", "587"))
    if not all([host, sender, username, password]):
        return {"sent": False, "reason": "SMTP not configured"}

    msg = EmailMessage()
    msg["Subject"] = "Attendance Alert"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(msg)
        return {"sent": True, "reason": "sent"}
    except Exception as exc:
        return {"sent": False, "reason": str(exc)}


def _send_sms(recipient: str | None, body: str) -> dict:
    if not recipient:
        return {"sent": False, "reason": "no recipient phone"}

    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    if not all([sid, token, from_number]):
        return {"sent": False, "reason": "Twilio not configured"}

    try:
        from twilio.rest import Client

        Client(sid, token).messages.create(body=body, from_=from_number, to=recipient)
        return {"sent": True, "reason": "sent"}
    except Exception as exc:
        return {"sent": False, "reason": str(exc)}
