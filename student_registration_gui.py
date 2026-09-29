"""
Student Registration GUI  –  AttendCam
Saves photos as:  known_faces/STU{ID}_{First_Last}.jpg
"""

import shutil
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import cv2
import face_recognition
from PIL import Image, ImageTk

import config
from db_manager import get_db_connection, init_db, register_student
from vision import VisionPipeline

# ── Colours ──────────────────────────────────────────────────────────────────
BG       = "#1a1a2e"
SURFACE  = "#22223b"
ACCENT   = "#533483"
SUCCESS  = "#22c55e"
WARNING  = "#f59e0b"
DANGER   = "#ef4444"
WHITE    = "#ffffff"
DIM      = "#94a3b8"
ENTRY_BG = "#0d1117"


def build_key(student_id: str, name: str) -> str:
    """STU001_John_Doe"""
    return f"STU{student_id.strip()}_{name.strip().replace(' ', '_')}"


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("AttendCam — Student Registration")
        self.root.geometry("1050x680")
        self.root.minsize(900, 580)
        self.root.configure(bg=BG)

        self._cap            = None
        self._webcam_active  = False
        self._current_frame  = None
        self._captured_frame = None
        self._import_path: Path | None = None

        init_db()
        self._build()
        self._refresh_list()
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

    # ══════════════════════════════════════════════════════════════════════════
    #  UI  BUILD
    # ══════════════════════════════════════════════════════════════════════════

    def _build(self) -> None:
        # ── Header bar ──────────────────────────────────────────────────────
        bar = tk.Frame(self.root, bg=ACCENT, height=58)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="🎓  AttendCam — Student Registration",
                 bg=ACCENT, fg=WHITE, font=("Segoe UI", 16, "bold")
                 ).pack(side="left", padx=20, pady=12)

        # ── Two-column body ──────────────────────────────────────────────────
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True)

        left  = tk.Frame(body, bg=BG, width=430)
        right = tk.Frame(body, bg=BG)
        left.pack(side="left",  fill="both",          padx=(16, 8), pady=14)
        right.pack(side="right", fill="both", expand=True, padx=(8, 16), pady=14)
        left.pack_propagate(False)

        self._build_left(left)
        self._build_right(right)

    # ── LEFT ─────────────────────────────────────────────────────────────────

    def _build_left(self, col: tk.Frame) -> None:

        # ╔══ Student Information ══╗
        info = tk.LabelFrame(col, text=" 📋 Student Information ",
                             bg=SURFACE, fg=WHITE,
                             font=("Segoe UI", 10, "bold"),
                             bd=2, relief="groove",
                             labelanchor="nw")
        info.pack(fill="x", pady=(0, 12))

        # Full Name
        tk.Label(info, text="Full Name", bg=SURFACE, fg=WHITE,
                 font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 2))
        self.name_var = tk.StringVar()
        tk.Entry(info, textvariable=self.name_var,
                 bg=ENTRY_BG, fg=WHITE, insertbackground=WHITE,
                 font=("Segoe UI", 12), relief="flat",
                 highlightthickness=2, highlightbackground="#3b3b6b",
                 highlightcolor=ACCENT).grid(
            row=1, column=0, sticky="ew", padx=14, pady=(0, 4))
        tk.Label(info, text="  e.g.  John Doe", bg=SURFACE, fg=DIM,
                 font=("Segoe UI", 8, "italic")).grid(
            row=2, column=0, sticky="w", padx=14)

        # Student ID
        tk.Label(info, text="Student ID  (numbers only)", bg=SURFACE, fg=WHITE,
                 font=("Segoe UI", 11, "bold")).grid(
            row=3, column=0, sticky="w", padx=14, pady=(12, 2))
        self.id_var = tk.StringVar()
        tk.Entry(info, textvariable=self.id_var,
                 bg=ENTRY_BG, fg=WHITE, insertbackground=WHITE,
                 font=("Segoe UI", 12), relief="flat",
                 highlightthickness=2, highlightbackground="#3b3b6b",
                 highlightcolor=ACCENT).grid(
            row=4, column=0, sticky="ew", padx=14, pady=(0, 4))
        tk.Label(info, text="  e.g.  001", bg=SURFACE, fg=DIM,
                 font=("Segoe UI", 8, "italic")).grid(
            row=5, column=0, sticky="w", padx=14)

        # Live filename preview
        self.key_var = tk.StringVar(value="Filename →  (fill in Name & ID above)")
        tk.Label(info, textvariable=self.key_var,
                 bg=SURFACE, fg="#7dd3fc",
                 font=("Consolas", 9)).grid(
            row=6, column=0, sticky="w", padx=14, pady=(10, 12))

        info.columnconfigure(0, weight=1)
        self.name_var.trace_add("write", self._update_key)
        self.id_var.trace_add("write",   self._update_key)

        # ╔══ Photo Source ══╗
        src = tk.LabelFrame(col, text=" 📷 Photo Source ",
                            bg=SURFACE, fg=WHITE,
                            font=("Segoe UI", 10, "bold"),
                            bd=2, relief="groove",
                            labelanchor="nw")
        src.pack(fill="x", pady=(0, 12))

        self.source_var = tk.StringVar(value="webcam")
        rb_row = tk.Frame(src, bg=SURFACE)
        rb_row.pack(fill="x", padx=14, pady=(10, 6))
        for lbl, val in [("📷  Webcam", "webcam"), ("🖼️  Import File", "file")]:
            tk.Radiobutton(rb_row, text=lbl, variable=self.source_var, value=val,
                           bg=SURFACE, fg=WHITE, selectcolor=ACCENT,
                           activebackground=SURFACE, activeforeground=WHITE,
                           font=("Segoe UI", 11),
                           command=self._toggle_source).pack(side="left", padx=(0, 20))

        # Webcam controls
        self.wc_row = tk.Frame(src, bg=SURFACE)
        self.wc_row.pack(fill="x", padx=14, pady=(0, 10))
        self.btn_start = self._btn(self.wc_row, "▶ Start Camera",   self._start_cam,  ACCENT)
        self.btn_cap   = self._btn(self.wc_row, "📸 Capture",       self._capture,    "#16a34a")
        self.btn_stop  = self._btn(self.wc_row, "⏹ Stop",           self._stop_cam,   DANGER)
        for b in (self.btn_start, self.btn_cap, self.btn_stop):
            b.pack(side="left", padx=(0, 6))
        self.btn_cap["state"]  = "disabled"
        self.btn_stop["state"] = "disabled"

        # File controls (hidden initially)
        self.file_row = tk.Frame(src, bg=SURFACE)
        self._btn(self.file_row, "📂 Browse Image", self._browse, ACCENT).pack(side="left", padx=(0, 10))
        self.file_lbl = tk.Label(self.file_row, text="No file selected",
                                  bg=SURFACE, fg=DIM, font=("Segoe UI", 10))
        self.file_lbl.pack(side="left")

        # ╔══ Photo Preview ══╗
        prev = tk.LabelFrame(col, text=" 🖼️ Photo Preview ",
                             bg=SURFACE, fg=WHITE,
                             font=("Segoe UI", 10, "bold"),
                             bd=2, relief="groove",
                             labelanchor="nw")
        prev.pack(fill="both", expand=True)

        self.preview = tk.Label(prev,
                                text="No preview yet\n\nStart webcam or import an image →",
                                bg="#070b14", fg=DIM, font=("Segoe UI", 10))
        self.preview.pack(fill="both", expand=True, padx=10, pady=(6, 4))

        self.face_var = tk.StringVar(value="")
        tk.Label(prev, textvariable=self.face_var,
                 bg=SURFACE, fg=SUCCESS, font=("Segoe UI", 9, "italic")
                 ).pack(pady=(0, 8))

    # ── RIGHT ────────────────────────────────────────────────────────────────

    def _build_right(self, col: tk.Frame) -> None:
        # Register button
        tk.Button(col, text="✅  Register Student", command=self._register,
                  bg=SUCCESS, fg=WHITE, font=("Segoe UI", 13, "bold"),
                  relief="flat", pady=10, cursor="hand2",
                  activebackground="#16a34a", activeforeground=WHITE
                  ).pack(fill="x", pady=(0, 12))

        # Status
        sf = tk.LabelFrame(col, text=" ℹ️ Status ",
                           bg=SURFACE, fg=WHITE, font=("Segoe UI", 10, "bold"),
                           bd=2, relief="groove", labelanchor="nw")
        sf.pack(fill="x", pady=(0, 12))

        self.status_var = tk.StringVar(value="Ready — enter Name & ID, then add a photo.")
        self.status_lbl = tk.Label(sf, textvariable=self.status_var,
                                   bg=SURFACE, fg=DIM,
                                   font=("Segoe UI", 10),
                                   wraplength=340, justify="left", anchor="w")
        self.status_lbl.pack(fill="x", padx=14, pady=10)

        # Student list
        lf = tk.LabelFrame(col, text=" 👥 Registered Students ",
                           bg=SURFACE, fg=WHITE, font=("Segoe UI", 10, "bold"),
                           bd=2, relief="groove", labelanchor="nw")
        lf.pack(fill="both", expand=True, pady=(0, 8))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("S.Treeview",
                        background=ENTRY_BG, foreground=WHITE,
                        fieldbackground=ENTRY_BG, rowheight=26,
                        font=("Segoe UI", 9))
        style.configure("S.Treeview.Heading",
                        background=ACCENT, foreground=WHITE,
                        font=("Segoe UI", 9, "bold"))
        style.map("S.Treeview", background=[("selected", "#7b52b9")])

        cols = ("Key", "Full Name", "Registered At")
        self.tree = ttk.Treeview(lf, columns=cols, show="headings",
                                 height=16, style="S.Treeview")
        self.tree.heading("Key",           text="File Key  (STU…)")
        self.tree.heading("Full Name",     text="Full Name")
        self.tree.heading("Registered At", text="Registered At")
        self.tree.column("Key",           width=160)
        self.tree.column("Full Name",     width=130)
        self.tree.column("Registered At", width=130, anchor="center")

        vsb = ttk.Scrollbar(lf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=(6, 12))
        vsb.pack(side="right", fill="y", pady=(6, 12), padx=(0, 10))

        tk.Button(col, text="🔄  Refresh List", command=self._refresh_list,
                  bg=ACCENT, fg=WHITE, font=("Segoe UI", 10, "bold"),
                  relief="flat", pady=6, cursor="hand2",
                  activebackground="#7b52b9", activeforeground=WHITE
                  ).pack(fill="x")

    # ══════════════════════════════════════════════════════════════════════════
    #  WIDGET HELPER
    # ══════════════════════════════════════════════════════════════════════════

    def _btn(self, parent, text, cmd, bg) -> tk.Button:
        b = tk.Button(parent, text=text, command=cmd,
                      bg=bg, fg=WHITE, font=("Segoe UI", 10, "bold"),
                      relief="flat", padx=8, pady=6, cursor="hand2",
                      activebackground="#7b52b9", activeforeground=WHITE)
        b.bind("<Enter>", lambda e: b.config(bg="#7b52b9") if str(b["state"]) != "disabled" else None)
        b.bind("<Leave>", lambda e: b.config(bg=bg)        if str(b["state"]) != "disabled" else None)
        return b

    # ══════════════════════════════════════════════════════════════════════════
    #  LOGIC
    # ══════════════════════════════════════════════════════════════════════════

    def _update_key(self, *_) -> None:
        sid  = self.id_var.get().strip()
        name = self.name_var.get().strip()
        if sid and name:
            self.key_var.set(f"Filename →  {build_key(sid, name)}.jpg")
        elif sid or name:
            self.key_var.set(f"Filename →  STU{sid}_{name.replace(' ', '_')}.jpg  (incomplete)")
        else:
            self.key_var.set("Filename →  (fill in Name & ID above)")

    def _toggle_source(self) -> None:
        if self.source_var.get() == "webcam":
            self.file_row.pack_forget()
            self.wc_row.pack(fill="x", padx=14, pady=(0, 10))
        else:
            self._stop_cam()
            self.wc_row.pack_forget()
            self.file_row.pack(fill="x", padx=14, pady=(0, 10))

    # ── Webcam ───────────────────────────────────────────────────────────────

    def _start_cam(self) -> None:
        if self._webcam_active:
            return
        self._cap = cv2.VideoCapture(config.CAMERA_INDEX)
        if not self._cap.isOpened():
            messagebox.showerror("Camera Error",
                                 f"Cannot open camera (index {config.CAMERA_INDEX}).")
            return
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  config.CAMERA_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
        self._webcam_active  = True
        self._captured_frame = None
        self.face_var.set("")
        self.btn_start["state"] = "disabled"
        self.btn_cap["state"]   = "normal"
        self.btn_stop["state"]  = "normal"
        self._status("Camera live — position student, then click 📸 Capture.", DIM)
        threading.Thread(target=self._cam_loop, daemon=True).start()

    def _cam_loop(self) -> None:
        while self._webcam_active:
            if not self._cap or not self._cap.isOpened():
                break
            ok, frame = self._cap.read()
            if not ok:
                break
            self._current_frame = frame
            self.root.after(0, self._push_preview)
            cv2.waitKey(33)

    def _push_preview(self) -> None:
        if self._webcam_active and self._current_frame is not None:
            self._show(self._current_frame)

    def _capture(self) -> None:
        if self._current_frame is None:
            messagebox.showwarning("No Frame", "Camera hasn't produced a frame yet.")
            return
        self._captured_frame = self._current_frame.copy()
        self._import_path    = None
        self._stop_cam()
        self._show(self._captured_frame)
        self._check_faces(self._captured_frame)

    def _stop_cam(self) -> None:
        self._webcam_active = False
        if self._cap:
            self._cap.release()
            self._cap = None
        self.btn_start["state"] = "normal"
        self.btn_cap["state"]   = "disabled"
        self.btn_stop["state"]  = "disabled"

    # ── File import ──────────────────────────────────────────────────────────

    def _browse(self) -> None:
        p = filedialog.askopenfilename(
            title="Select Student Photo",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp"), ("All", "*.*")])
        if not p:
            return
        path = Path(p)
        self._import_path    = path
        self._captured_frame = None
        self.file_lbl.config(text=path.name, fg=WHITE)
        img = cv2.imread(str(path))
        if img is None:
            messagebox.showerror("Error", f"Cannot read: {path.name}")
            return
        self._show(img)
        self._check_faces(img)

    # ── Preview ──────────────────────────────────────────────────────────────

    def _show(self, bgr) -> None:
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        w   = max(self.preview.winfo_width(),  380)
        h   = max(self.preview.winfo_height(), 240)
        pil.thumbnail((w, h), Image.LANCZOS)
        ph  = ImageTk.PhotoImage(pil)
        self.preview.config(image=ph, text="")
        self.preview.image = ph

    def _check_faces(self, bgr) -> None:
        def _run():
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            n   = len(face_recognition.face_locations(rgb))
            if n == 0:
                msg, col = "⚠️  No face detected — retake", DANGER
            elif n > 1:
                msg, col = f"⚠️  {n} faces — use solo photo", WARNING
            else:
                msg, col = "✅  Face detected — ready to register", SUCCESS
            self.root.after(0, lambda: self.face_var.set(msg))
            self.root.after(0, lambda: self._status(msg, col))
        threading.Thread(target=_run, daemon=True).start()

    # ── Register ─────────────────────────────────────────────────────────────

    def _register(self) -> None:
        name = self.name_var.get().strip()
        sid  = self.id_var.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Please enter the student's Full Name.")
            return
        if not sid:
            messagebox.showwarning("Missing", "Please enter the Student ID.")
            return

        key = build_key(sid, name)   # e.g. STU001_John_Doe

        if self.source_var.get() == "webcam":
            if self._captured_frame is None:
                messagebox.showwarning("No Photo", "Capture a webcam photo first.")
                return
            bgr      = self._captured_frame
            src_file = None
        else:
            if self._import_path is None:
                messagebox.showwarning("No Photo", "Browse and select an image first.")
                return
            src_file = self._import_path
            bgr      = cv2.imread(str(src_file))
            if bgr is None:
                messagebox.showerror("Error", f"Cannot read: {src_file.name}")
                return

        # Face check
        rgb   = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        faces = face_recognition.face_locations(rgb)
        if len(faces) == 0:
            messagebox.showerror("No Face",
                "No face detected.\nUse a clear, well-lit photo.")
            return
        if len(faces) > 1:
            if not messagebox.askyesno("Multiple Faces",
                    f"{len(faces)} faces found.\nContinue anyway?"):
                return

        # Save → known_faces/STU001_John_Doe.jpg
        suffix = src_file.suffix.lower() if src_file else ".jpg"
        dest   = config.KNOWN_FACES_DIR / f"{key}{suffix}"
        try:
            if src_file:
                shutil.copy2(src_file, dest)
            else:
                cv2.imwrite(str(dest), bgr)
        except Exception as ex:
            messagebox.showerror("Save Error", str(ex))
            return

        # DB
        try:
            register_student(key, name, str(dest))
        except Exception as ex:
            messagebox.showerror("DB Error", str(ex))
            return

        # Reload encodings
        try:
            VisionPipeline(force_reload=True)
        except Exception:
            pass

        self._status(f"✅  Registered '{name}'  →  {dest.name}", SUCCESS)
        messagebox.showinfo("Done!", f"'{name}' registered!\n\nSaved as:\n  {dest.name}")

        # Reset
        self.name_var.set("")
        self.id_var.set("")
        self._captured_frame = None
        self._import_path    = None
        self.file_lbl.config(text="No file selected", fg=DIM)
        self.face_var.set("")
        self.preview.config(image="",
            text="No preview yet\n\nStart webcam or import an image →")
        self.preview.image = None
        self._refresh_list()

    # ── Student list ─────────────────────────────────────────────────────────

    def _refresh_list(self) -> None:
        self.tree.delete(*self.tree.get_children())
        try:
            with get_db_connection() as conn:
                rows = conn.execute(
                    "SELECT student_id, name, registered_at "
                    "FROM students ORDER BY registered_at DESC"
                ).fetchall()
            for r in rows:
                ts = (r["registered_at"] or "").split(".")[0]
                self.tree.insert("", "end", values=(r["student_id"], r["name"], ts))
        except Exception as ex:
            self._status(f"⚠️  {ex}", WARNING)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _status(self, msg: str, color: str = DIM) -> None:
        self.status_var.set(msg)
        self.status_lbl.config(fg=color)

    def _quit(self) -> None:
        self._stop_cam()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
