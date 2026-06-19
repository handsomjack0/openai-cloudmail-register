#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import register as runner_config  # noqa: E402
from services.register import openai_register  # noqa: E402
from services.register.mail_provider import create_mailbox, release_mailbox, wait_for_code  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe whether OpenAI OTP reaches CloudMail")
    parser.add_argument("--config", default=str(ROOT / "config.json"))
    parser.add_argument("--username", default="")
    parser.add_argument("--timeout", type=float, default=None)
    args = parser.parse_args()

    raw = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
    cfg, _ = runner_config._build_register_config(raw, argparse.Namespace(total=1, threads=1, proxy=None))
    if args.timeout is not None:
        cfg["mail"]["wait_timeout"] = args.timeout
    runner_config._validate_config(cfg)
    openai_register.config.update({"mail": cfg["mail"], "proxy": cfg["proxy"], "total": 1, "threads": 1})

    registrar = openai_register.PlatformRegistrar(cfg["proxy"])
    mailbox = create_mailbox(cfg["mail"], args.username.strip() or None)
    try:
        email = str(mailbox.get("address") or "")
        print(f"[mailbox] {email}")
        registrar._platform_authorize(email, 1)
        registrar._register_user(email, openai_register._random_password(), 1)
        registrar._send_otp(1)
        code = wait_for_code(cfg["mail"], mailbox)
        if not code:
            print(
                "[result] failed: wait_otp_timeout "
                f"raw={mailbox.get('_cloudmail_last_raw_count', 'unknown')} "
                f"matched={mailbox.get('_cloudmail_last_matched_count', 'unknown')}"
            )
            return 1
        print(f"[result] received_code={code}")
        return 0
    except Exception:
        release_mailbox(mailbox)
        raise
    finally:
        registrar.close()


if __name__ == "__main__":
    raise SystemExit(main())
