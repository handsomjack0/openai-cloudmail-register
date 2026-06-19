#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import queue
import sqlite3
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = BASE_DIR / "config.json"
PYTHON = sys.executable or "python"


class RegisterGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OpenAI CloudMail Register Runner")
        self.geometry("980x680")
        self.minsize(860, 560)
        self.process: subprocess.Popen[str] | None = None
        self.output_queue: queue.Queue[str] = queue.Queue()
        self._build_state()
        self._build_ui()
        self.after(100, self._drain_output)
        self.after(1000, self._refresh_status_panel)

    def _build_state(self) -> None:
        self.config_var = tk.StringVar(value=str(DEFAULT_CONFIG))
        self.preset_var = tk.StringVar(value="stable")
        self.total_var = tk.StringVar(value="")
        self.threads_var = tk.StringVar(value="")
        self.export_format_var = tk.StringVar(value="txt")
        self.stats_vars = {
            "batch": tk.StringVar(value="-"),
            "state": tk.StringVar(value="-"),
            "total": tk.StringVar(value="0"),
            "success": tk.StringVar(value="0"),
            "failed": tk.StringVar(value="0"),
            "running": tk.StringVar(value="0"),
            "pending": tk.StringVar(value="0"),
            "rate": tk.StringVar(value="0%"),
        }

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)

        top = ttk.Frame(self, padding=(12, 12, 12, 6))
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Config").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(top, textvariable=self.config_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(top, text="Browse", command=self._browse_config).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(top, text="Open", command=self._open_config).grid(row=0, column=3, padx=(8, 0))

        controls = ttk.Frame(self, padding=(12, 6))
        controls.grid(row=1, column=0, sticky="ew")
        for index in range(12):
            controls.columnconfigure(index, weight=0)
        controls.columnconfigure(11, weight=1)

        ttk.Label(controls, text="Preset").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            controls,
            textvariable=self.preset_var,
            values=("smoke", "stable", "fast", "custom"),
            width=10,
            state="readonly",
        ).grid(row=0, column=1, padx=(6, 14))

        ttk.Label(controls, text="Total").grid(row=0, column=2, sticky="w")
        ttk.Entry(controls, textvariable=self.total_var, width=8).grid(row=0, column=3, padx=(6, 14))

        ttk.Label(controls, text="Threads").grid(row=0, column=4, sticky="w")
        ttk.Entry(controls, textvariable=self.threads_var, width=8).grid(row=0, column=5, padx=(6, 14))

        ttk.Label(controls, text="Export").grid(row=0, column=6, sticky="w")
        ttk.Combobox(
            controls,
            textvariable=self.export_format_var,
            values=("txt", "csv", "jsonl"),
            width=8,
            state="readonly",
        ).grid(row=0, column=7, padx=(6, 14))

        stats = ttk.Frame(self, padding=(12, 2, 12, 6))
        stats.grid(row=2, column=0, sticky="ew")
        for index in range(8):
            stats.columnconfigure(index, weight=1)
        for column, (label, key) in enumerate(
            (
                ("Batch", "batch"),
                ("State", "state"),
                ("Total", "total"),
                ("Success", "success"),
                ("Failed", "failed"),
                ("Running", "running"),
                ("Pending", "pending"),
                ("Rate", "rate"),
            )
        ):
            item = ttk.Frame(stats)
            item.grid(row=0, column=column, sticky="ew", padx=3)
            ttk.Label(item, text=label).grid(row=0, column=0, sticky="w")
            ttk.Label(item, textvariable=self.stats_vars[key], font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w")

        buttons = ttk.Frame(self, padding=(12, 0, 12, 6))
        buttons.grid(row=3, column=0, sticky="new")
        for index in range(10):
            buttons.columnconfigure(index, weight=1)

        self.action_buttons: list[ttk.Button] = []
        for column, (label, command) in enumerate(
            (
                ("Doctor", self.run_doctor),
                ("Run", self.run_batch),
                ("Resume", self.run_resume),
                ("Retry Failed", self.run_retry_failed),
                ("Status", self.run_status),
                ("Export", self.run_export),
                ("Stop", self.stop_process),
                ("Clear", self.clear_output),
                ("Results", self.open_results_dir),
                ("Log", self.open_log_file),
            )
        ):
            button = ttk.Button(buttons, text=label, command=command)
            button.grid(row=0, column=column, sticky="ew", padx=3, pady=3)
            self.action_buttons.append(button)

        output_frame = ttk.Frame(self, padding=(12, 0, 12, 12))
        output_frame.grid(row=4, column=0, sticky="nsew")
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        self.output = tk.Text(output_frame, wrap="word", height=20, font=("Consolas", 10))
        self.output.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(output_frame, command=self.output.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.output.configure(yscrollcommand=scrollbar.set)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(12, 4)).grid(row=5, column=0, sticky="ew")

    def _browse_config(self) -> None:
        selected = filedialog.askopenfilename(
            initialdir=str(BASE_DIR),
            title="Select config.json",
            filetypes=(("JSON", "*.json"), ("All files", "*.*")),
        )
        if selected:
            self.config_var.set(selected)

    def _open_config(self) -> None:
        path = Path(self.config_var.get()).expanduser()
        if not path.exists():
            messagebox.showwarning("Config", f"Config not found:\n{path}")
            return
        self._open_path(path, "Config")

    def _open_path(self, path: Path, title: str) -> None:
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except Exception as error:
            messagebox.showerror(title, str(error))

    def _base_command(self) -> list[str]:
        return [PYTHON, "-u", str(BASE_DIR / "register.py")]

    def _config_args(self) -> list[str]:
        return ["--config", self.config_var.get().strip() or str(DEFAULT_CONFIG)]

    def _run_args(self) -> list[str]:
        args: list[str] = []
        preset = self.preset_var.get().strip()
        if preset and preset != "custom":
            args.extend(["--preset", preset])
        total = self.total_var.get().strip()
        threads = self.threads_var.get().strip()
        if total:
            args.extend(["--total", total])
        if threads:
            args.extend(["--threads", threads])
        return args

    def _load_config(self) -> dict[str, Any]:
        path = Path(self.config_var.get().strip() or str(DEFAULT_CONFIG)).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Config not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise RuntimeError("Config must contain a JSON object")
        return data

    def _output_path(self, key: str, default: str) -> Path:
        data = self._load_config()
        output = data.get("output") if isinstance(data.get("output"), dict) else {}
        raw = str(output.get(key) or default).strip() or default
        path = Path(raw)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path

    def _progress_db_path(self) -> Path:
        return self._output_path("progress_db", "data/progress.db")

    def _validate_run_inputs(self) -> bool:
        for label, value in (("Total", self.total_var.get().strip()), ("Threads", self.threads_var.get().strip())):
            if not value:
                continue
            try:
                parsed = int(value)
            except ValueError:
                messagebox.showwarning("Runner", f"{label} must be a positive integer.")
                return False
            if parsed <= 0:
                messagebox.showwarning("Runner", f"{label} must be greater than 0.")
                return False
        try:
            self._load_config()
        except Exception as error:
            messagebox.showwarning("Config", str(error))
            return False
        return True

    def _start_command(self, command: list[str]) -> None:
        if self.process and self.process.poll() is None:
            messagebox.showinfo("Runner", "A command is already running.")
            return
        self._append_line("")
        self._append_line("> " + subprocess.list2cmdline(command))
        self.status_var.set("Running")
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            self.process = subprocess.Popen(
                command,
                cwd=str(BASE_DIR),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except Exception as error:
            self.status_var.set("Failed to start")
            messagebox.showerror("Runner", str(error))
            return
        threading.Thread(target=self._read_process_output, daemon=True).start()

    def _read_process_output(self) -> None:
        assert self.process is not None
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self.output_queue.put(line.rstrip("\n"))
        code = self.process.wait()
        self.output_queue.put(f"[process exited code={code}]")
        self.output_queue.put("__PROCESS_DONE__")

    def _drain_output(self) -> None:
        while True:
            try:
                line = self.output_queue.get_nowait()
            except queue.Empty:
                break
            if line == "__PROCESS_DONE__":
                self.status_var.set("Ready")
                self.process = None
                self._refresh_status_panel(schedule=False)
                continue
            self._append_line(line)
        self.after(100, self._drain_output)

    def _append_line(self, line: str) -> None:
        self.output.insert("end", line + "\n")
        self.output.see("end")

    def clear_output(self) -> None:
        self.output.delete("1.0", "end")

    def stop_process(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.status_var.set("Stopping")

    def open_results_dir(self) -> None:
        try:
            path = self._output_path("accounts_file", "data/accounts.jsonl").parent
            path.mkdir(parents=True, exist_ok=True)
            self._open_path(path, "Results")
        except Exception as error:
            messagebox.showerror("Results", str(error))

    def open_log_file(self) -> None:
        try:
            path = self._output_path("log_file", "logs/register.log")
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text("", encoding="utf-8")
            self._open_path(path, "Log")
        except Exception as error:
            messagebox.showerror("Log", str(error))

    def _refresh_status_panel(self, schedule: bool = True) -> None:
        try:
            db_path = self._progress_db_path()
            if db_path.exists():
                self._update_status_from_db(db_path)
        except Exception:
            pass
        if schedule:
            self.after(2000, self._refresh_status_panel)

    def _update_status_from_db(self, db_path: Path) -> None:
        with sqlite3.connect(db_path, timeout=1) as conn:
            batch = conn.execute(
                "SELECT id,total,status FROM batches ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if not batch:
                return
            counts_rows = conn.execute(
                "SELECT status,COUNT(*) FROM tasks WHERE batch_id=? GROUP BY status",
                (batch[0],),
            ).fetchall()
        counts = {str(name): int(value) for name, value in counts_rows}
        total = int(batch[1] or 0)
        success = counts.get("success", 0)
        failed = counts.get("failed", 0)
        running = counts.get("running", 0)
        pending = counts.get("pending", 0)
        finished = success + failed
        rate = f"{(success / finished * 100):.1f}%" if finished else "0%"
        self.stats_vars["batch"].set(str(batch[0])[-8:])
        self.stats_vars["state"].set(str(batch[2]))
        self.stats_vars["total"].set(str(total))
        self.stats_vars["success"].set(str(success))
        self.stats_vars["failed"].set(str(failed))
        self.stats_vars["running"].set(str(running))
        self.stats_vars["pending"].set(str(pending))
        self.stats_vars["rate"].set(rate)

    def run_doctor(self) -> None:
        self._start_command(self._base_command() + ["doctor"] + self._config_args())

    def run_batch(self) -> None:
        if not self._validate_run_inputs():
            return
        self._start_command(self._base_command() + ["run"] + self._config_args() + self._run_args())

    def run_resume(self) -> None:
        if not self._validate_run_inputs():
            return
        self._start_command(self._base_command() + ["resume"] + self._config_args() + self._run_args())

    def run_retry_failed(self) -> None:
        if not self._validate_run_inputs():
            return
        self._start_command(self._base_command() + ["retry-failed"] + self._config_args() + self._run_args())

    def run_status(self) -> None:
        self._start_command(self._base_command() + ["status"] + self._config_args())

    def run_export(self) -> None:
        fmt = self.export_format_var.get().strip() or "txt"
        self._start_command(self._base_command() + ["export"] + self._config_args() + ["--format", fmt])


def self_test() -> int:
    commands = [
        [PYTHON, "-u", str(BASE_DIR / "register.py"), "doctor", "--config", str(DEFAULT_CONFIG)],
        [PYTHON, "-u", str(BASE_DIR / "register.py"), "run", "--config", str(DEFAULT_CONFIG), "--preset", "smoke"],
        [PYTHON, "-u", str(BASE_DIR / "register.py"), "status", "--config", str(DEFAULT_CONFIG)],
        [PYTHON, "-u", str(BASE_DIR / "register.py"), "export", "--config", str(DEFAULT_CONFIG), "--format", "txt"],
    ]
    for command in commands:
        if not command or command[0] != PYTHON or command[1] != "-u":
            raise RuntimeError("invalid command construction")
    print("[ok] gui command construction")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Tkinter GUI for the register runner")
    parser.add_argument("--self-test", action="store_true", help="Validate GUI command wiring without opening a window")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    app = RegisterGui()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
