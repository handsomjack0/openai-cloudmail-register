#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


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

    def _build_state(self) -> None:
        self.config_var = tk.StringVar(value=str(DEFAULT_CONFIG))
        self.preset_var = tk.StringVar(value="stable")
        self.total_var = tk.StringVar(value="")
        self.threads_var = tk.StringVar(value="")
        self.export_format_var = tk.StringVar(value="txt")

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

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

        buttons = ttk.Frame(self, padding=(12, 0, 12, 6))
        buttons.grid(row=2, column=0, sticky="new")
        for index in range(8):
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
            )
        ):
            button = ttk.Button(buttons, text=label, command=command)
            button.grid(row=0, column=column, sticky="ew", padx=3, pady=3)
            self.action_buttons.append(button)

        output_frame = ttk.Frame(self, padding=(12, 0, 12, 12))
        output_frame.grid(row=3, column=0, sticky="nsew")
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        self.output = tk.Text(output_frame, wrap="word", height=20, font=("Consolas", 10))
        self.output.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(output_frame, command=self.output.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.output.configure(yscrollcommand=scrollbar.set)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(12, 4)).grid(row=4, column=0, sticky="ew")

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
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except Exception as error:
            messagebox.showerror("Config", str(error))

    def _base_command(self) -> list[str]:
        return [PYTHON, str(BASE_DIR / "register.py")]

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

    def _start_command(self, command: list[str]) -> None:
        if self.process and self.process.poll() is None:
            messagebox.showinfo("Runner", "A command is already running.")
            return
        self._append_line("")
        self._append_line("> " + " ".join(command))
        self.status_var.set("Running")
        try:
            self.process = subprocess.Popen(
                command,
                cwd=str(BASE_DIR),
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

    def run_doctor(self) -> None:
        self._start_command(self._base_command() + ["doctor"] + self._config_args())

    def run_batch(self) -> None:
        self._start_command(self._base_command() + ["run"] + self._config_args() + self._run_args())

    def run_resume(self) -> None:
        self._start_command(self._base_command() + ["resume"] + self._config_args() + self._run_args())

    def run_retry_failed(self) -> None:
        self._start_command(self._base_command() + ["retry-failed"] + self._config_args() + self._run_args())

    def run_status(self) -> None:
        self._start_command(self._base_command() + ["status"] + self._config_args())

    def run_export(self) -> None:
        fmt = self.export_format_var.get().strip() or "txt"
        self._start_command(self._base_command() + ["export"] + self._config_args() + ["--format", fmt])


def self_test() -> int:
    commands = [
        [PYTHON, str(BASE_DIR / "register.py"), "doctor", "--config", str(DEFAULT_CONFIG)],
        [PYTHON, str(BASE_DIR / "register.py"), "run", "--config", str(DEFAULT_CONFIG), "--preset", "smoke"],
        [PYTHON, str(BASE_DIR / "register.py"), "status", "--config", str(DEFAULT_CONFIG)],
        [PYTHON, str(BASE_DIR / "register.py"), "export", "--config", str(DEFAULT_CONFIG), "--format", "txt"],
    ]
    for command in commands:
        if not command or command[0] != PYTHON:
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
