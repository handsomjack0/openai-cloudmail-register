# OpenAI CloudMail Register Runner

Standalone Python runner for the CloudMail-based OpenAI registration flow.

## Setup

```bash
python -m pip install -r requirements.txt
copy config.example.json config.json
```

Fill `config.json` with your local CloudMail and proxy settings. Do not commit
`config.json` or files under `data/`.

## Run

```bash
python register.py --config config.json
```

Overrides:

```bash
python register.py --total 20 --threads 2
python register.py --proxy http://127.0.0.1:7890
python register.py --check-config
```

Successful accounts are appended to `data/accounts.jsonl`. Failed tasks are
appended to `data/failed.jsonl`. Runtime logs are written to `logs/register.log`.

## Diagnostics

Create a CloudMail mailbox and wait for any 6-digit code:

```bash
python scripts/check_cloudmail.py --config config.json
```

Probe OpenAI OTP delivery without completing the full account creation:

```bash
python scripts/probe_openai_delivery.py --config config.json
```

## Notes

- This first version intentionally has no Docker, no web UI, and no dependency
  on Chatgpt2api.
- The copied registration core keeps the previously working stage metrics:
  `create_mailbox_ms`, `authorize_ms`, `register_user_ms`, `send_otp_ms`,
  `wait_otp_ms`, `validate_otp_ms`, `create_account_ms`, `exchange_token_ms`.
