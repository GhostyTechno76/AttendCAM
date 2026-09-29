# Autonomous Attendance Camera System (3/6 Interval Rule)

A modular, production-ready attendance camera system using Python, OpenCV, `face_recognition`, and SQLite — now with a full **graphical interface** for launching all tools from one place.

---

## Features
- **GUI Launcher** — One-click access to all system tools from a single window (`launcher.py`).
- **Student Registration GUI** — Add students by name & ID, capture their photo via webcam or import an existing image, with live face validation.
- **Instant Webcam Frame Capture** — Consumes warmup frames to stabilize auto-exposure and immediately releases the hardware.
- **Deep Face Recognition** — 128-dimensional facial embedding matching via dlib / `face_recognition` with fast disk caching.
- **3/6 Interval Tracking Logic** — Captures a snapshot every 10 minutes over a 1-hour session (6 total intervals). If a student is detected in **≥ 3** intervals they are marked **`Present`**; otherwise **`Absent`**.
- **Automatic Hourly Reset** — Persists results to SQLite and resets counters for the next session.
- **Audit Trail** — Saves hourly summaries and granular interval snapshots with annotated debug frames.

---

## Directory Structure
```
AttendCam/
├── known_faces/                    # Student reference images
│   └── STU001_John_Doe.jpg         # Format: STU{ID}_{First_Last}.jpg
├── database/
│   ├── attendance.db               # SQLite database
│   ├── face_encodings_cache.pkl    # Fast encodings cache
│   └── captures/                   # Timestamped annotated debug frames
├── launcher.py                     # ★ Main GUI hub — start here
├── student_registration_gui.py     # Student registration GUI
├── config.py                       # Central settings
├── db_manager.py                   # SQLite tables & CRUD operations
├── vision.py                       # OpenCV capture & face_recognition embeddings
├── tracker.py                      # 3/6 Interval state machine & summary logic
├── scheduler.py                    # 10-minute automated schedule runner
├── main.py                         # Main application entry point
├── register_student.py             # CLI student registration tool
└── test_system.py                  # Automated test suite
```

## Standalone Downloadable Executable (`AttendCamBeta.exe`)

You can run AttendCam directly without installing Python or any dependencies:

```powershell
# Double-click or run from terminal:
.\AttendCamBeta.exe
```

To re-build the executable at any time:
```powershell
.\.venv\Scripts\pyinstaller.exe AttendCamBeta.spec
```

---

## Quick Start — GUI (Recommended)

Launch the main hub and access everything from one window:

```powershell
.venv\Scripts\python.exe launcher.py
# OR
.\AttendCamBeta.exe
```

### Launcher buttons

| Button | Action |
|---|---|
| **👤 Add Face** | Opens the Student Registration GUI in a new window |
| **📷 Test** | Runs a single on-demand capture to verify camera & face detection |
| **⏱️ Time Test** | Runs a full 6-interval simulation with 5-second gaps |
| **📋 History** | Shows a colour-coded table of recent attendance records |
| **🚀 Start** | Launches the live 10-minute interval attendance camera |

> Test, Time Test, and Start open in a **new console window** so you can see live logs.

---

## Student Registration GUI

From the launcher click **Add Face**, or run directly:

```powershell
.venv\Scripts\python.exe student_registration_gui.py
```

1. Enter **Full Name** (e.g. `John Doe`) and **Student ID** (e.g. `001`).
2. A live preview shows the filename: `STU001_John_Doe.jpg`.
3. Choose **Webcam** → Start Camera → position student → **Capture**, **or** choose **Import File** → Browse.
4. The GUI validates that exactly one face is present.
5. Click **Register Student** — the photo is saved to `known_faces/` and the student is added to the SQLite database.

---

## CLI Usage (Advanced)

### Register a student (CLI)
```powershell
# Capture via webcam
.venv\Scripts\python.exe register_student.py --id STU001_John_Doe --name "John Doe"

# Import existing photo
.venv\Scripts\python.exe register_student.py --id STU001_John_Doe --name "John Doe" --from-file "C:\path\to\photo.jpg"

# List registered students
.venv\Scripts\python.exe register_student.py --list
```

### Run autonomous attendance
```powershell
.venv\Scripts\python.exe main.py
```
*(Immediate first capture, then every 10 minutes. Press `Ctrl+C` to exit cleanly.)*

### Single test capture
```powershell
.venv\Scripts\python.exe scheduler.py --capture-now
```

### 6-interval simulation test (~30 seconds)
```powershell
.venv\Scripts\python.exe scheduler.py --test
```

### View attendance history
```powershell
.venv\Scripts\python.exe scheduler.py --history
```

---

## Configuration

All tunable settings are in [`config.py`](config.py):

| Setting | Default | Description |
|---|---|---|
| `CAMERA_INDEX` | `0` | Webcam index |
| `FACE_MATCH_TOLERANCE` | `0.55` | Lower = stricter matching |
| `FACE_DETECTION_MODEL` | `"hog"` | `"hog"` (CPU) or `"cnn"` (GPU) |
| `INTERVAL_MINUTES` | `10` | Minutes between captures |
| `TOTAL_INTERVALS_PER_SESSION` | `6` | Intervals per 1-hour session |
| `REQUIRED_DETECTIONS_FOR_PRESENT` | `3` | Min detections to mark Present |
