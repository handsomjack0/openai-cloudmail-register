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

Desktop GUI:

```bash
python gui.py
```

On Windows you can also double-click:

```text
start.bat
start_gui.bat
start_cli.bat
```

`start.bat` and `start_gui.bat` open the GUI. `start_cli.bat` opens a small
command menu for common operations.

CLI:

```bash
python register.py run --config config.json
```

Legacy mode still works:

```bash
python register.py --config config.json --total 20 --threads 2
```

Common commands:

```bash
python register.py doctor
python register.py run --preset smoke
python register.py run --preset stable
python register.py run --preset fast
python register.py resume
python register.py retry-failed
python register.py status
python register.py export --format txt
```

Successful accounts are appended to `data/accounts.jsonl`. Failed tasks are
appended to `data/failed.jsonl`. Runtime logs are written to `logs/register.log`.
Batch progress is stored in `data/progress.db`.

## Recommended Flow

1. Open the GUI:

   ```bash
   python gui.py
   ```

2. Validate the config:

   ```bash
   python register.py doctor
   ```

3. Run one account:

   ```bash
   python register.py run --preset smoke
   ```

4. Run a small batch:

   ```bash
   python register.py run --total 5 --threads 1
   ```

5. Run normal batches:

   ```bash
   python register.py run --preset stable
   ```

6. Resume after interruption:

   ```bash
   python register.py resume
   ```

7. Retry failed tasks only:

   ```bash
   python register.py retry-failed
   ```

8. Export accounts:

   ```bash
   python register.py export --format txt
   python register.py export --format csv
   python register.py export --format jsonl
   ```

## Presets

- `smoke`: `total=1`, `threads=1`, mailbox pool disabled.
- `stable`: `total=20`, `threads=2`, mailbox pool size 10.
- `fast`: `total=50`, `threads=4`, mailbox pool size 20.

## Stability Features

- `gui.py` is a thin Tkinter wrapper around the same CLI commands, so GUI and
  CLI behavior stay aligned.
- Network-like failures are retried per task. Configure with
  `register.max_task_retries` and `register.retry_backoff_seconds`.
- SQLite progress tracking records every task in `output.progress_db`.
- `--resume` reruns unfinished or failed tasks from the latest unfinished batch.
- `register.auto_stop_on_consecutive_failures` stops long bad runs early.
- `register.email_pool_size` pre-creates CloudMail mailboxes in the background
  so workers can start registration faster. The pool only activates when the
  active provider is a single `cloudmail_gen`; other providers keep the original
  creation path. `register.email_pool_warmup_seconds` can wait briefly for the
  first pooled mailbox before workers start. `register.email_pool_low_watermark`
  controls when the pool starts refilling.
- `status` reads `data/progress.db` and prints batch counts plus recent failures.
- `retry-failed` reruns only failed tasks from the latest unfinished batch.
- `export` converts `data/accounts.jsonl` into txt, csv, or jsonl output.

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
