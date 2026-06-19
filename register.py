#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.account_service import account_service
from services.register import openai_register


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = BASE_DIR / "config.json"
EXAMPLE_CONFIG = BASE_DIR / "config.example.json"


def _force_utf8_stdio() -> None:
    if sys.platform != "win32":
        return
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist. Copy config.example.json to config.json first.")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return data


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _resolve_path(value: str | Path, default: str) -> Path:
    raw = str(value or default).strip() or default
    path = Path(raw)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def _build_register_config(raw: dict[str, Any], args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Path]]:
    cloudmail = raw.get("cloudmail") if isinstance(raw.get("cloudmail"), dict) else {}
    register = raw.get("register") if isinstance(raw.get("register"), dict) else {}
    proxy_cfg = raw.get("proxy") if isinstance(raw.get("proxy"), dict) else {}
    output = raw.get("output") if isinstance(raw.get("output"), dict) else {}

    proxy_url = str(args.proxy if args.proxy is not None else proxy_cfg.get("url") or "").strip()
    if proxy_cfg.get("enabled") is False and args.proxy is None:
        proxy_url = ""

    total = args.total if args.total is not None else register.get("total", 1)
    threads = args.threads if args.threads is not None else register.get("threads", 1)

    mail_conf = {
        "request_timeout": float(register.get("request_timeout") or 30),
        "wait_timeout": float(register.get("otp_timeout") or register.get("wait_timeout") or 60),
        "wait_interval": float(register.get("otp_normal_poll_interval") or 2),
        "fast_wait_seconds": float(register.get("otp_fast_poll_seconds") or 10),
        "fast_wait_interval": float(register.get("otp_fast_poll_interval") or 0.8),
        "providers": [
            {
                "enable": True,
                "type": "cloudmail_gen",
                "api_base": str(cloudmail.get("api_base") or "").rstrip("/"),
                "admin_email": str(cloudmail.get("admin_email") or ""),
                "admin_password": str(cloudmail.get("admin_password") or ""),
                "domain": _as_list(cloudmail.get("domains") or cloudmail.get("domain")),
                "subdomain": _as_list(cloudmail.get("subdomains") or cloudmail.get("subdomain")),
                "email_prefix": str(cloudmail.get("email_prefix") or ""),
                "auto_add_account": cloudmail.get("auto_add_account", True) is not False,
                "account_add_token": str(cloudmail.get("account_add_token") or ""),
            }
        ],
    }
    if proxy_url:
        mail_conf["proxy"] = proxy_url

    cfg = {
        "mail": mail_conf,
        "proxy": proxy_url,
        "total": max(1, int(total or 1)),
        "threads": max(1, int(threads or 1)),
        "otp_resend": str(register.get("otp_resend") or "after_delay").strip().lower(),
        "otp_resend_delay": max(0, int(float(register.get("otp_resend_delay") or 5))),
        "thread_start_interval": max(0.0, float(register.get("thread_start_interval") or 0)),
        "auto_stop_on_consecutive_failures": max(0, int(register.get("auto_stop_on_consecutive_failures") or 0)),
    }

    paths = {
        "accounts_file": _resolve_path(output.get("accounts_file", ""), "data/accounts.jsonl"),
        "failed_file": _resolve_path(output.get("failed_file", ""), "data/failed.jsonl"),
        "log_file": _resolve_path(output.get("log_file", ""), "logs/register.log"),
    }
    return cfg, paths


def _validate_config(cfg: dict[str, Any]) -> None:
    provider = (cfg.get("mail", {}).get("providers") or [{}])[0]
    missing = [
        name
        for name in ("api_base", "admin_email", "admin_password")
        if not str(provider.get(name) or "").strip()
    ]
    if not provider.get("domain"):
        missing.append("domains")
    if missing:
        raise RuntimeError("missing CloudMail config: " + ", ".join(missing))
    mode = str(cfg.get("otp_resend") or "").strip().lower()
    if mode not in {"always", "after_delay", "off"}:
        raise RuntimeError("register.otp_resend must be one of: always, after_delay, off")


def _append_jsonl(path: Path, item: dict[str, Any], lock: threading.Lock) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with lock, path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")


def _install_log_sink(log_file: Path) -> None:
    log_lock = threading.Lock()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    def sink(text: str, color: str = "") -> None:
        safe_text = str(text).encode("utf-8", errors="replace").decode("utf-8", errors="replace")
        line = {
            "time": datetime.now(timezone.utc).isoformat(),
            "level": color or "info",
            "message": safe_text,
        }
        with log_lock, log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=True, separators=(",", ":")) + "\n")

    openai_register.register_log_sink = sink


def _run(cfg: dict[str, Any], paths: dict[str, Path]) -> int:
    account_service.configure(paths["accounts_file"])
    _install_log_sink(paths["log_file"])
    openai_register.config.update(
        {
            "mail": cfg["mail"],
            "proxy": cfg["proxy"],
            "total": cfg["total"],
            "threads": cfg["threads"],
            "otp_resend": cfg["otp_resend"],
            "otp_resend_delay": cfg["otp_resend_delay"],
        }
    )
    openai_register.reset_stats(time.time())

    total = int(cfg["total"])
    threads = min(int(cfg["threads"]), total)
    start_interval = float(cfg["thread_start_interval"])
    auto_stop = int(cfg["auto_stop_on_consecutive_failures"])
    failed_lock = threading.Lock()
    consecutive_failures = 0
    submitted = 0
    completed = 0
    success = 0
    fail = 0

    print(f"[runner] total={total} threads={threads} proxy={'on' if cfg['proxy'] else 'off'}")
    print(f"[runner] accounts={paths['accounts_file']}")
    print(f"[runner] failed={paths['failed_file']}")
    print(f"[runner] log={paths['log_file']}")

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {}

        def submit_next() -> bool:
            nonlocal submitted
            if submitted >= total:
                return False
            submitted += 1
            futures[executor.submit(openai_register.worker, submitted)] = submitted
            if start_interval > 0 and submitted < total:
                time.sleep(start_interval)
            return True

        while len(futures) < threads and submit_next():
            pass

        while futures:
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                index = futures.pop(future)
                completed += 1
                try:
                    result = future.result()
                except Exception as error:
                    result = {"ok": False, "index": index, "stage": "runner", "error": str(error)}

                if result.get("ok"):
                    success += 1
                    consecutive_failures = 0
                else:
                    fail += 1
                    consecutive_failures += 1
                    _append_jsonl(
                        paths["failed_file"],
                        {
                            "index": result.get("index", index),
                            "stage": result.get("stage") or "unknown",
                            "error": result.get("error") or "",
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        },
                        failed_lock,
                    )

                if auto_stop and consecutive_failures >= auto_stop:
                    print(f"[runner] stop: consecutive failures reached {consecutive_failures}")
                    for pending in futures:
                        pending.cancel()
                    futures.clear()
                    break

                if submitted < total:
                    submit_next()

    extra = openai_register.snapshot_extra_stats()
    print("")
    print("[summary]")
    print(f"done={completed} success={success} fail={fail}")
    print("avg_stage_ms=" + json.dumps(extra.get("avg_stage_ms", {}), ensure_ascii=False))
    print("last_errors_by_stage=" + json.dumps(extra.get("last_errors_by_stage", {}), ensure_ascii=False))
    print("mailbox_provider_success=" + json.dumps(extra.get("mailbox_provider_success", {}), ensure_ascii=False))
    print(f"otp_wait_avg_seconds={extra.get('otp_wait_avg_seconds', 0)}")
    return 0 if fail == 0 and success > 0 else 1


def main() -> int:
    _force_utf8_stdio()
    parser = argparse.ArgumentParser(description="Standalone CloudMail OpenAI register runner")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.json")
    parser.add_argument("--total", type=int, default=None, help="Override register.total")
    parser.add_argument("--threads", type=int, default=None, help="Override register.threads")
    parser.add_argument("--proxy", default=None, help="Override proxy.url; pass an empty string for direct")
    parser.add_argument("--check-config", action="store_true", help="Only load and validate config")
    args = parser.parse_args()

    raw = _load_json(Path(args.config))
    cfg, paths = _build_register_config(raw, args)
    _validate_config(cfg)
    if args.check_config:
        print("[ok] config valid")
        return 0
    return _run(cfg, paths)


if __name__ == "__main__":
    raise SystemExit(main())
