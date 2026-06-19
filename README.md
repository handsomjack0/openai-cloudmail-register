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
python register.py --resume
```

Successful accounts are appended to `data/accounts.jsonl`. Failed tasks are
appended to `data/failed.jsonl`. Runtime logs are written to `logs/register.log`.
Batch progress is stored in `data/progress.db`.

## Recommended Flow

1. Validate the config:

   ```bash
   python register.py --check-config
   ```

2. Run one account:

   ```bash
   python register.py --total 1 --threads 1
   ```

3. Run a small batch:

   ```bash
   python register.py --total 5 --threads 1
   ```

4. Run normal batches:

   ```bash
   python register.py --total 20 --threads 2
   ```

5. Resume after interruption:

   ```bash
   python register.py --resume
   ```

## Stability Features

- Network-like failures are retried per task. Configure with
  `register.max_task_retries` and `register.retry_backoff_seconds`.
- SQLite progress tracking records every task in `output.progress_db`.
- `--resume` reruns unfinished or failed tasks from the latest unfinished batch.
- `register.auto_stop_on_consecutive_failures` stops long bad runs early.
- `register.email_pool_size` pre-creates CloudMail mailboxes in the background
  so workers can start registration faster. The pool only activates when the
  active provider is a single `cloudmail_gen`; other providers keep the original
  creation path. `register.email_pool_warmup_seconds` can wait briefly for the
  first pooled mailbox before workers start.

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
- CloudMail is the optimized default path, but the provider module keeps the
  original compatibility surface for older configs and helper scripts.
- The registration core keeps the previously working stage metrics:
  `create_mailbox_ms`, `authorize_ms`, `register_user_ms`, `send_otp_ms`,
  `wait_otp_ms`, `validate_otp_ms`, `create_account_ms`, `exchange_token_ms`.
- Keep these files private and untracked:
  `config.json`, `data/*.jsonl`, `data/*.db`, and `logs/`.
