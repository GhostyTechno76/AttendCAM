"""
AttendCam — Main Launcher GUI
Central hub to launch all AttendCam tools from one window.
"""

import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

# ── Resolve paths ─────────────────────────────────────────────────────────────
BASE = Path(__file__).resolve().parent
PYTHON = sys.executable          # same venv interpreter that launched this GUI

# ── Palette ───────────────────────────────────────────────────────────────────
BG        = "#1a1a2e"
SURFACE   = "#16213e"
CARD      = "#0f3460"
ACCENT    = "#533483"
SUCCESS   = "#16a34a"
WARNING   = "#d97706"
DANGER    = "#dc2626"
INFO      = "#0891b2"
WHITE     = "#ffffff"
DIM       = "#94a3b8"

# (label, icon, description, bg_color, action_key)
BUTTONS = [
    (
        "Add Face",
        "👤",
        "Register a new student:\nenter Name & ID, then\ncapture or import a photo.",
        ACCENT,
        "register",
    ),
    (
        "Test",
        "📷",
        "Single on-demand capture:\nverify camera & face\ndetection right now.",
        INFO,
        "capture_now",
    ),
    (
        "Time Test",
        "⏱️",
        "Full 6-interval simulation\nwith 5-second gaps to\ncheck the whole pipeline.",
        WARNING,
        "test",
    ),
    (
        "History",
        "📋",
        "View recent hourly\nattendance records\nfrom the database.",
        "#7c3aed",
        "history",
    ),
    (
        "Start",
        "🚀",
        "Launch the live attendance\ncamera (10-min intervals,\nruns until Ctrl+C).",
        SUCCESS,
        "start",
    ),
]


class LauncherGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("AttendCam — Launcher")
        self.root.geometry("700x480")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        self._build()

    # ══════════════════════════════════════════════════════════════════════════

    def _build(self) -> None:
        # ── Header ──
        hdr = tk.Frame(self.root, bg=ACCENT, height=70)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="🎓  AttendCam",
                 bg=ACCENT, fg=WHITE, font=("Segoe UI", 22, "bold")
                 ).pack(side="left", padx=24, pady=14)
        tk.Label(hdr, text="Autonomous Attendance Camera System",
                 bg=ACCENT, fg="#d8b4fe", font=("Segoe UI", 11)
                 ).pack(side="left", pady=22)

        # ── Button grid ──
        grid = tk.Frame(self.root, bg=BG)
        grid.pack(fill="both", expand=True, padx=28, pady=24)

        for col in range(5):
            grid.columnconfigure(col, weight=1, uniform="col")

        for i, (label, icon, desc, color, key) in enumerate(BUTTONS):
            self._tile(grid, label, icon, desc, color, key, col=i)

        # ── Footer / status ──
        foot = tk.Frame(self.root, bg=SURFACE, height=38)
        foot.pack(fill="x", side="bottom")
        foot.pack_propagate(False)

        self.status_var = tk.StringVar(value="Select an action above to get started.")
        tk.Label(foot, textvariable=self.status_var,
                 bg=SURFACE, fg=DIM, font=("Segoe UI", 9)
                 ).pack(side="left", padx=16, pady=10)

    def _tile(self, parent, label, icon, desc, color, key, col) -> None:
        """Creates a single large card button."""
        card = tk.Frame(parent, bg=CARD, bd=0, cursor="hand2")
        card.grid(row=0, column=col, padx=6, pady=0, sticky="nsew")
        parent.rowconfigure(0, weight=1)

        # Coloured top stripe
        stripe = tk.Frame(card, bg=color, height=6)
        stripe.pack(fill="x")

        # Icon
        tk.Label(card, text=icon, bg=CARD, fg=WHITE,
                 font=("Segoe UI Emoji", 28)).pack(pady=(18, 4))

        # Title
        tk.Label(card, text=label, bg=CARD, fg=WHITE,
                 font=("Segoe UI", 13, "bold")).pack()

        # Description
        tk.Label(card, text=desc, bg=CARD, fg=DIM,
                 font=("Segoe UI", 8), justify="center"
                 ).pack(padx=8, pady=(6, 14))

        # Click button
        btn = tk.Button(card, text=f"Open  {label}",
                        command=lambda k=key, l=label: self._launch(k, l),
                        bg=color, fg=WHITE,
                        font=("Segoe UI", 9, "bold"),
                        relief="flat", pady=6, cursor="hand2",
                        activebackground=BG, activeforeground=WHITE)
        btn.pack(fill="x", padx=12, pady=(0, 14))

        # Hover glow on entire card
        for widget in (card, stripe, btn):
            widget.bind("<Enter>", lambda e, c=card, col=color: self._hover(c, col, True))
            widget.bind("<Leave>", lambda e, c=card, col=color: self._hover(c, col, False))

    def _hover(self, card: tk.Frame, color: str, entering: bool) -> None:
        bg = "#1a2540" if entering else CARD
        for child in card.winfo_children():
            try:
                if isinstance(child, tk.Frame):   # stripe — keep its colour
                    pass
                elif isinstance(child, tk.Button):
                    pass
                else:
                    child.config(bg=bg)
            except tk.TclError:
                pass
        card.config(bg=bg)

    # ══════════════════════════════════════════════════════════════════════════
    #  ACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def _launch(self, key: str, label: str) -> None:
        self.status_var.set(f"Launching  '{label}'…")
        self.root.update_idletasks()

        try:
            if key == "register":
                self._open_register_gui()
            elif key == "capture_now":
                self._run_in_terminal("scheduler.py", "--capture-now", label)
            elif key == "test":
                self._run_in_terminal("scheduler.py", "--test", label)
            elif key == "history":
                self._show_history()
            elif key == "start":
                self._run_in_terminal("main.py", "", label)
        except Exception as ex:
            messagebox.showerror("Launch Error", str(ex))
            self.status_var.set("Error — see dialog.")

    # ── Register GUI (in-process, opens new Tk Toplevel) ─────────────────────

    def _open_register_gui(self) -> None:
        # Import here so the main launcher doesn't pull in cv2 at startup
        try:
            import student_registration_gui as srg
        except ImportError as ex:
            messagebox.showerror("Import Error",
                f"Cannot load student_registration_gui.py:\n{ex}")
            return

        win = tk.Toplevel(self.root)
        srg.App(win)
        self.status_var.set("Student Registration window opened.")

    # ── Terminal-style runner (new console window on Windows) ─────────────────

    def _run_in_terminal(self, script: str, flag: str, label: str) -> None:
        """
        Opens a new console window so the user can see live output
        (logging, face detection results, etc.).
        """
        script_path = BASE / script
        if not script_path.exists():
            messagebox.showerror("Not Found", f"Script not found:\n{script_path}")
            return

        cmd = [PYTHON, str(script_path)]
        if flag:
            cmd.append(flag)

        if sys.platform == "win32":
            # Open in a new cmd window so logs are visible
            subprocess.Popen(
                ["cmd", "/k"] + cmd,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                cwd=str(BASE),
            )
        else:
            subprocess.Popen(cmd, cwd=str(BASE))

        self.status_var.set(f"'{label}' launched in a new terminal window.")

    # ── History (shown in a scrollable Toplevel) ──────────────────────────────

    def _show_history(self) -> None:
        try:
            import db_manager
            records = db_manager.get_latest_hourly_summaries(limit=50)
        except Exception as ex:
            messagebox.showerror("DB Error", str(ex))
            return

        win = tk.Toplevel(self.root)
        win.title("AttendCam — Attendance History")
        win.geometry("820x480")
        win.configure(bg=BG)

        tk.Label(win, text="📋  Attendance History",
                 bg=BG, fg=WHITE, font=("Segoe UI", 14, "bold")
                 ).pack(pady=(14, 6), padx=16, anchor="w")

        from tkinter import ttk
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("H.Treeview",
                        background="#0d1117", foreground=WHITE,
                        fieldbackground="#0d1117", rowheight=26,
                        font=("Consolas", 9))
        style.configure("H.Treeview.Heading",
                        background=ACCENT, foreground=WHITE,
                        font=("Segoe UI", 9, "bold"))
        style.map("H.Treeview", background=[("selected", ACCENT)])

        cols = ("Session", "Student ID", "Name", "Detections", "Status", "Marked At")
        tree = ttk.Treeview(win, columns=cols, show="headings",
                             style="H.Treeview")
        for c, w in zip(cols, [180, 140, 130, 90, 80, 150]):
            tree.heading(c, text=c)
            tree.column(c, width=w, anchor="center")

        vsb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        if not records:
            tree.insert("", "end", values=("—", "No records yet", "", "", "", ""))
        else:
            for r in records:
                det = f"{r['detection_count']}/{r['total_intervals']}"
                ts  = (r["marked_at"] or "").split(".")[0]
                fg_tag = "present" if r["status"] == "Present" else "absent"
                tree.insert("", "end", tag=fg_tag,
                            values=(r["session_id"], r["student_id"],
                                    r.get("name", ""), det, r["status"], ts))
            tree.tag_configure("present", foreground=SUCCESS)
            tree.tag_configure("absent",  foreground=DANGER)

        tree.pack(side="left", fill="both", expand=True, padx=(16, 0), pady=(0, 16))
        vsb.pack(side="right", fill="y", pady=(0, 16), padx=(0, 14))

        tk.Button(win, text="Close", command=win.destroy,
                  bg=ACCENT, fg=WHITE, font=("Segoe UI", 10, "bold"),
                  relief="flat", pady=6, cursor="hand2"
                  ).pack(pady=(0, 14))

        self.status_var.set("History window opened.")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    root = tk.Tk()
    LauncherGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
