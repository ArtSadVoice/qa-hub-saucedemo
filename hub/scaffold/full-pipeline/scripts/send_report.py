"""
send_report.py — ส่ง Word report ผ่าน Email และ/หรือ Slack
Usage:
    python scripts/send_report.py                        # ส่ง report ล่าสุดใน output/
    python scripts/send_report.py output/Report.docx     # ระบุไฟล์
    python scripts/send_report.py --channel slack        # ส่งเฉพาะ Slack
    python scripts/send_report.py --channel email        # ส่งเฉพาะ Email
    python scripts/send_report.py --channel both         # ส่งทั้งคู่ (default)
"""

import sys, json, smtplib, argparse, requests
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DIST_FILE = BASE_DIR / "docs" / "distribution.json"
OUTPUT_DIR = BASE_DIR / "output"


def load_config():
    if not DIST_FILE.exists():
        print("❌ ไม่พบ docs/distribution.json — รัน /start หรือสร้างไฟล์ก่อน")
        sys.exit(1)
    return json.loads(DIST_FILE.read_text(encoding="utf-8"))


def find_latest_report():
    reports = sorted(OUTPUT_DIR.glob("*.docx"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not reports:
        print("❌ ไม่พบ .docx ใน output/ — รัน /report ก่อน")
        sys.exit(1)
    return reports[0]


def send_email(report_path: Path, cfg: dict):
    smtp_cfg = cfg.get("smtp", {})
    host = smtp_cfg.get("host", "")
    port = smtp_cfg.get("port", 587)
    user = smtp_cfg.get("user", "")
    password = smtp_cfg.get("password", "")
    recipients = cfg.get("report_recipients", [])
    project = cfg.get("project", "Project")

    if not host or not user or not password:
        print("⚠️  Email: SMTP ยังไม่ได้ตั้งค่าใน docs/distribution.json — ข้าม")
        return False
    if not recipients:
        print("⚠️  Email: ไม่มี report_recipients — ข้าม")
        return False

    msg = MIMEMultipart()
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = f"[QA Report] {project} — {datetime.now().strftime('%Y-%m-%d')}"

    body = (
        f"สวัสดี,\n\n"
        f"แนบ QA Test Report สำหรับโปรเจค {project}\n"
        f"วันที่: {datetime.now().strftime('%d %B %Y')}\n"
        f"ไฟล์: {report_path.name}\n\n"
        f"กรุณาตรวจสอบผลการทดสอบในไฟล์แนบ\n"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with open(report_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{report_path.name}"')
    msg.attach(part)

    try:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, recipients, msg.as_string())
        print(f"✅ Email ส่งถึง: {', '.join(recipients)}")
        return True
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False


def send_slack(report_path: Path, cfg: dict):
    webhook = cfg.get("slack_webhook", "")
    channel = cfg.get("slack_channel", "#qa-reports")
    project = cfg.get("project", "Project")

    if not webhook:
        print("⚠️  Slack: slack_webhook ยังไม่ได้ตั้งค่าใน docs/distribution.json — ข้าม")
        return False

    text = (
        f"📊 *QA Report พร้อมแล้ว — {project}*\n"
        f"วันที่: {datetime.now().strftime('%d %B %Y')}\n"
        f"ไฟล์: `{report_path.name}`\n"
        f"Channel: {channel}\n\n"
        f"> รับไฟล์ได้จาก QA Team หรือ Hub Dashboard"
    )

    try:
        resp = requests.post(webhook, json={"text": text}, timeout=10)
        if resp.status_code == 200:
            print(f"✅ Slack notification ส่งไปที่ {channel}")
            return True
        else:
            print(f"❌ Slack error: HTTP {resp.status_code} — {resp.text}")
            return False
    except Exception as e:
        print(f"❌ Slack error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Send QA Report")
    parser.add_argument("report", nargs="?", help="Path to .docx report (optional)")
    parser.add_argument("--channel", choices=["email", "slack", "both"], default="both")
    args = parser.parse_args()

    cfg = load_config()
    report_path = Path(args.report) if args.report else find_latest_report()

    if not report_path.exists():
        print(f"❌ ไม่พบไฟล์: {report_path}")
        sys.exit(1)

    print(f"\n📤 ส่ง report: {report_path.name}")
    print(f"   Channel: {args.channel}\n")

    results = {}
    if args.channel in ("email", "both"):
        results["email"] = send_email(report_path, cfg)
    if args.channel in ("slack", "both"):
        results["slack"] = send_slack(report_path, cfg)

    ok = all(v for v in results.values() if v is not None)
    print(f"\n{'✅ ส่งสำเร็จ' if ok else '⚠️  ส่งบางส่วน — ตรวจสอบข้อความข้างบน'}")


if __name__ == "__main__":
    main()
