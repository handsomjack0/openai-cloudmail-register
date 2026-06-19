#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import string
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.register.mail_provider import create_mailbox, wait_for_code  # noqa: E402


def _load_mail_config(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    cloudmail = raw.get("cloudmail") if isinstance(raw.get("cloudmail"), dict) else {}
    register = raw.get("register") if isinstance(raw.get("register"), dict) else {}
    proxy = raw.get("proxy") if isinstance(raw.get("proxy"), dict) else {}
    proxy_url = str(proxy.get("url") or "").strip() if proxy.get("enabled") is not False else ""
    return {
        "request_timeout": 30,
        "wait_timeout": float(register.get("otp_timeout") or 120),
        "wait_interval": float(register.get("otp_normal_poll_interval") or 2),
        "fast_wait_seconds": float(register.get("otp_fast_poll_seconds") or 10),
        "fast_wait_interval": float(register.get("otp_fast_poll_interval") or 0.8),
        "proxy": proxy_url,
        "providers": [
            {
                "enable": True,
                "type": "cloudmail_gen",
                "api_base": str(cloudmail.get("api_base") or "").rstrip("/"),
                "admin_email": str(cloudmail.get("admin_email") or ""),
                "admin_password": str(cloudmail.get("admin_password") or ""),
                "domain": cloudmail.get("domains") or cloudmail.get("domain") or [],
                "email_prefix": str(cloudmail.get("email_prefix") or "probe"),
                "auto_add_account": cloudmail.get("auto_add_account", True) is not False,
                "account_add_token": str(cloudmail.get("account_add_token") or ""),
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a CloudMail mailbox and poll for an OTP-like code")
    parser.add_argument("--config", default=str(ROOT / "config.json"))
    parser.add_argument("--username", default="")
    parser.add_argument("--timeout", type=float, default=None)
    args = parser.parse_args()

    mail_config = _load_mail_config(Path(args.config))
    if args.timeout is not None:
        mail_config["wait_timeout"] = args.timeout

    username = args.username.strip() or "probe" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    mailbox = create_mailbox(mail_config, username)
    print(f"[mailbox] {mailbox.get('address')}")
    print("[action] send a message containing a 6-digit code to this mailbox now")
    started = time.time()
    code = wait_for_code(mail_config, mailbox)
    if not code:
        print(f"[result] no code received in {time.time() - started:.1f}s")
        print(
            "[debug] "
            f"raw={mailbox.get('_cloudmail_last_raw_count', 'unknown')} "
            f"matched={mailbox.get('_cloudmail_last_matched_count', 'unknown')} "
            f"subject={mailbox.get('_cloudmail_last_subject', '')}"
        )
        return 1
    print(f"[result] code={code} wait={time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
