"""
SAM Desktop GUI Application.
Provides a modern native Windows GUI interface for Project SAM without requiring CMD or terminal.
Zero external GUI dependencies (uses standard library Tkinter).
Supports interactive conversation, Windows computer control, voice activation, and safety gating.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, Optional

from src.sam import __version__
from src.sam.main import SAMSystem

logger = logging.getLogger("sam.gui")


class SAMGuiApp:
    """Desktop GUI interface for SAM JARVIS assistant."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"SAM — JARVIS AI Assistant (v{__version__})")
        self.root.geometry("820x720")
        self.root.minsize(620, 520)
        self.root.configure(bg="#0F172A")

        # System state
        self.sam = SAMSystem()
        self.is_processing = False
        self.voice_running = False
        self.pending_confirmation: Optional[str] = None
        self.msg_queue: queue.Queue[tuple[str, Any]] = queue.Queue()

        self._apply_styles()
        self._build_ui()
        self._bind_events()

        # Start message polling loop
        self.root.after(100, self._process_queue)

        # Welcome message
        self._add_system_message(
            f"⚡ SAM v{__version__} Systems Online.\n"
            "AI Brain: Ready (Ollama Local/Cloud Fallback)\n"
            "Memory: SQLite WAL + Vector Cosine Store Active\n"
            "Safety Guard: Windows Protection Enabled\n"
            "Type a command below, click a quick action, or toggle Voice Mode!"
        )

    def _apply_styles(self) -> None:
        """Configure ttk styles for a sleek dark theme."""
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")

        # Frame styles
        self.style.configure("TFrame", background="#0F172A")
        self.style.configure("Header.TFrame", background="#1E293B")
        self.style.configure("Bar.TFrame", background="#1E293B")
        self.style.configure("Card.TFrame", background="#1E293B")

        # Label styles
        self.style.configure("HeaderTitle.TLabel", background="#1E293B", foreground="#38BDF8", font=("Segoe UI", 16, "bold"))
        self.style.configure("HeaderSub.TLabel", background="#1E293B", foreground="#94A3B8", font=("Segoe UI", 9))
        self.style.configure("Status.TLabel", background="#1E293B", foreground="#10B981", font=("Segoe UI", 9, "bold"))

        # Button styles
        self.style.configure("Primary.TButton", background="#0284C7", foreground="#FFFFFF", font=("Segoe UI", 10, "bold"), borderwidth=0)
        self.style.map("Primary.TButton", background=[("active", "#0369A1"), ("disabled", "#334155")])

        self.style.configure("Chip.TButton", background="#334155", foreground="#E2E8F0", font=("Segoe UI", 8), borderwidth=0)
        self.style.map("Chip.TButton", background=[("active", "#475569")])

        self.style.configure("Voice.TButton", background="#059669", foreground="#FFFFFF", font=("Segoe UI", 9, "bold"), borderwidth=0)
        self.style.map("Voice.TButton", background=[("active", "#047857")])

        self.style.configure("Danger.TButton", background="#DC2626", foreground="#FFFFFF", font=("Segoe UI", 9, "bold"), borderwidth=0)
        self.style.map("Danger.TButton", background=[("active", "#B91C1C")])

    def _build_ui(self) -> None:
        """Assemble header, action chips, chat area, and input controls."""
        # 1. Header Frame
        header = ttk.Frame(self.root, style="Header.TFrame", padding=(16, 12))
        header.pack(fill=tk.X, side=tk.TOP)

        title_box = ttk.Frame(header, style="Header.TFrame")
        title_box.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Label(title_box, text="⚡ SAM", style="HeaderTitle.TLabel").pack(anchor=tk.W)
        ttk.Label(title_box, text="Local Autonomous JARVIS for Windows", style="HeaderSub.TLabel").pack(anchor=tk.W)

        # Status & Voice Controls in Header
        ctrl_box = ttk.Frame(header, style="Header.TFrame")
        ctrl_box.pack(side=tk.RIGHT, fill=tk.Y)

        self.status_label = ttk.Label(ctrl_box, text="🟢 System Ready", style="Status.TLabel")
        self.status_label.pack(side=tk.LEFT, padx=(0, 14))

        self.voice_btn = ttk.Button(
            ctrl_box,
            text="🎙️ Voice Mode",
            style="Voice.TButton",
            command=self._toggle_voice_mode
        )
        self.voice_btn.pack(side=tk.RIGHT)

        # 2. Quick Action Chips Bar
        chips_frame = ttk.Frame(self.root, padding=(16, 8))
        chips_frame.pack(fill=tk.X, side=tk.TOP)

        chips = [
            ("🌐 Open Chrome", "Open Chrome"),
            ("📊 System Load", "What is my CPU usage?"),
            ("👁️ Screen Vision", "Inspect screen"),
            ("🧠 Recall Memory", "What do you remember about my notes?"),
            ("🧹 Clear Chat", "__clear__"),
        ]

        for label, cmd in chips:
            btn = ttk.Button(
                chips_frame,
                text=label,
                style="Chip.TButton",
                command=lambda c=cmd: self._handle_chip_click(c)
            )
            btn.pack(side=tk.LEFT, padx=3)

        # 3. Confirmation Alert Bar (Hidden by default)
        self.confirm_frame = ttk.Frame(self.root, style="Card.TFrame", padding=(14, 8))
        self.confirm_label = tk.Label(
            self.confirm_frame,
            text="",
            bg="#1E293B",
            fg="#F87171",
            font=("Segoe UI", 9, "bold"),
            wraplength=520,
            justify=tk.LEFT
        )
        self.confirm_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_confirm_yes = ttk.Button(
            self.confirm_frame,
            text="Confirm Action",
            style="Danger.TButton",
            command=self._execute_confirmed_action
        )
        self.btn_confirm_yes.pack(side=tk.RIGHT, padx=4)

        self.btn_confirm_no = ttk.Button(
            self.confirm_frame,
            text="Cancel",
            style="Chip.TButton",
            command=self._cancel_confirmed_action
        )
        self.btn_confirm_no.pack(side=tk.RIGHT, padx=4)

        # 4. Chat Feed
        chat_frame = ttk.Frame(self.root, padding=(16, 4))
        chat_frame.pack(fill=tk.BOTH, expand=True)

        self.chat_text = tk.Text(
            chat_frame,
            bg="#0B132B",
            fg="#F8FAFC",
            insertbackground="#38BDF8",
            font=("Segoe UI", 10),
            wrap=tk.WORD,
            borderwidth=0,
            padx=12,
            pady=12,
            relief=tk.FLAT
        )
        self.chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(chat_frame, orient=tk.VERTICAL, command=self.chat_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_text.configure(yscrollcommand=scrollbar.set)

        # Text styles & tags
        self.chat_text.tag_configure("system", foreground="#64748B", font=("Segoe UI", 9, "italic"))
        self.chat_text.tag_configure("user_header", foreground="#38BDF8", font=("Segoe UI", 9, "bold"))
        self.chat_text.tag_configure("user_msg", foreground="#E2E8F0", font=("Segoe UI", 10))
        self.chat_text.tag_configure("sam_header", foreground="#10B981", font=("Segoe UI", 9, "bold"))
        self.chat_text.tag_configure("sam_msg", foreground="#F8FAFC", font=("Segoe UI", 10))
        self.chat_text.tag_configure("warning", foreground="#EF4444", font=("Segoe UI", 9, "bold"))
        self.chat_text.tag_configure("action", foreground="#FBBF24", font=("Segoe UI", 9))
        self.chat_text.config(state=tk.DISABLED)

        # 5. Input Frame
        input_frame = ttk.Frame(self.root, padding=(16, 12))
        input_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(
            input_frame,
            textvariable=self.entry_var,
            bg="#1E293B",
            fg="#FFFFFF",
            insertbackground="#38BDF8",
            font=("Segoe UI", 11),
            relief=tk.FLAT,
            borderwidth=8
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        self.send_btn = ttk.Button(
            input_frame,
            text="Send 🚀",
            style="Primary.TButton",
            command=self._on_send_click
        )
        self.send_btn.pack(side=tk.RIGHT)

    def _bind_events(self) -> None:
        """Bind keyboard shortcuts and window close handlers."""
        self.entry.bind("<Return>", lambda e: self._on_send_click())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.entry.focus_set()

    def _handle_chip_click(self, cmd: str) -> None:
        if cmd == "__clear__":
            self._clear_chat()
            return
        self.entry_var.set(cmd)
        self._on_send_click()

    def _clear_chat(self) -> None:
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.delete("1.0", tk.END)
        self.chat_text.config(state=tk.DISABLED)
        self._add_system_message("Chat cleared.")

    def _on_send_click(self) -> None:
        text = self.entry_var.get().strip()
        if not text or self.is_processing:
            return

        self.entry_var.set("")
        self._add_user_message(text)
        self._dispatch_command(text, user_confirmed=False)

    def _dispatch_command(self, user_input: str, user_confirmed: bool = False) -> None:
        """Executes a command asynchronously without blocking the UI."""
        self.is_processing = True
        self.send_btn.state(["disabled"])
        self.status_label.config(text="⚙️ Processing...", foreground="#F59E0B")

        def _worker():
            try:
                turn = self.sam.process_turn(user_input, user_confirmed=user_confirmed)
                self.msg_queue.put(("turn_result", (user_input, turn)))
            except Exception as e:
                logger.exception("Error during SAM processing: %s", e)
                self.msg_queue.put(("error", str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _process_queue(self) -> None:
        """Poll the thread message queue and update UI safely."""
        try:
            while not self.msg_queue.empty():
                msg_type, data = self.msg_queue.get_nowait()
                if msg_type == "turn_result":
                    user_input, turn = data
                    self._handle_turn_result(user_input, turn)
                elif msg_type == "voice_reply":
                    self._add_sam_message(data)
                elif msg_type == "voice_status":
                    self.status_label.config(text=data[0], foreground=data[1])
                elif msg_type == "error":
                    self._add_system_message(f"[ERROR] {data}")
                    self.is_processing = False
                    self.send_btn.state(["!disabled"])
                    self.status_label.config(text="🟢 System Ready", foreground="#10B981")
        finally:
            self.root.after(100, self._process_queue)

    def _handle_turn_result(self, user_input: str, turn: Dict[str, Any]) -> None:
        self.is_processing = False
        self.send_btn.state(["!disabled"])
        self.status_label.config(text="🟢 System Ready", foreground="#10B981")

        # Check if blocked for confirmation
        if turn.get("blocked"):
            prompt = turn.get("response_text", "High-risk action blocked.")
            self.pending_confirmation = user_input
            self.confirm_label.config(text=f"⚠️ {prompt}")
            self.confirm_frame.pack(fill=tk.X, side=tk.TOP, before=self.chat_text.master)
            self._add_warning_message(f"[SAFETY GUARD] {prompt}")
            return

        # If previously showing confirmation, hide it
        self._hide_confirmation()

        response = turn.get("styled_response") or turn.get("response_text", "Done.")
        self._add_sam_message(response)

        # Log tool output if executed
        if turn.get("executed") and turn.get("output"):
            self._add_action_message(f"Action Output: {turn.get('output')}")

    def _execute_confirmed_action(self) -> None:
        if not self.pending_confirmation:
            return
        cmd = self.pending_confirmation
        self._hide_confirmation()
        self._add_system_message("User confirmed action execution.")
        self._dispatch_command(cmd, user_confirmed=True)

    def _cancel_confirmed_action(self) -> None:
        self._hide_confirmation()
        self._add_system_message("Action cancelled by user.")

    def _hide_confirmation(self) -> None:
        self.pending_confirmation = None
        self.confirm_frame.pack_forget()

    def _toggle_voice_mode(self) -> None:
        if self.voice_running:
            self.voice_running = False
            self.voice_btn.config(text="🎙️ Voice Mode", style="Voice.TButton")
            self.status_label.config(text="🟢 System Ready", foreground="#10B981")
            self._add_system_message("Voice mode deactivated.")
        else:
            self.voice_running = True
            self.voice_btn.config(text="🛑 Stop Voice", style="Danger.TButton")
            self.status_label.config(text="🎙️ Listening ('Hey SAM')...", foreground="#38BDF8")
            self._add_system_message("Voice mode active. Say 'Hey SAM'...")

            def _voice_loop():
                while self.voice_running:
                    try:
                        self.msg_queue.put(("voice_status", ("🎙️ Listening ('Hey SAM')...", "#38BDF8")))
                        resp = self.sam.start_voice_session()
                        if resp and self.voice_running:
                            self.msg_queue.put(("voice_reply", resp))
                    except Exception as e:
                        logger.debug("Voice loop tick: %s", e)
                    time.sleep(1)

            threading.Thread(target=_voice_loop, daemon=True).start()

    def _add_user_message(self, text: str) -> None:
        self.chat_text.config(state=tk.NORMAL)
        t_str = time.strftime("%H:%M")
        self.chat_text.insert(tk.END, f"\nUser [{t_str}]:\n", "user_header")
        self.chat_text.insert(tk.END, f"{text}\n", "user_msg")
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)

    def _add_sam_message(self, text: str) -> None:
        self.chat_text.config(state=tk.NORMAL)
        t_str = time.strftime("%H:%M")
        self.chat_text.insert(tk.END, f"\nSAM [{t_str}]:\n", "sam_header")
        self.chat_text.insert(tk.END, f"{text}\n", "sam_msg")
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)

    def _add_system_message(self, text: str) -> None:
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.insert(tk.END, f"\n[SYSTEM] {text}\n", "system")
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)

    def _add_warning_message(self, text: str) -> None:
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.insert(tk.END, f"\n{text}\n", "warning")
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)

    def _add_action_message(self, text: str) -> None:
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.insert(tk.END, f"  ↳ {text}\n", "action")
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)

    def _on_close(self) -> None:
        self.voice_running = False
        try:
            self.sam.close()
        except Exception:
            pass
        self.root.destroy()


def run_gui() -> None:
    """Launch SAM GUI application."""
    root = tk.Tk()
    app = SAMGuiApp(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
