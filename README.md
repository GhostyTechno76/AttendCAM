# Autonomous Attendance Camera System (3/6 Interval Rule)

A modular, production-ready attendance camera system using Python, OpenCV, `face_recognition`, and SQLite.

## Features
- **Instant Webcam Frame Capture**: Consumes warmup frames to stabilize auto-exposure and immediately releases the hardware.
- **Deep Face Recognition**: 128-dimensional facial embedding matching via dlib/`face_recognition` with fast disk caching.
- **3/6 Interval Tracking Logic**: Captures a snapshot every 10 minutes over a 1-hour session (6 total intervals). If a student is detected in **$\ge 3$** intervals, they are marked **`Present`**; otherwise **`Absent`**.
- **Automatic Hourly Reset**: Persists results to SQLite and resets counters for the next hour session.
- **Audit Trail**: Saves both high-level hourly decisions and granular interval detection snapshots with annotated debug frames.
- **Interactive Registration**: Snap student photos via webcam or import existing images with face detection validation.

---

## Directory Structure
```
AttendCam/
├── known_faces/                # Student reference image directory
│   ├── STU001_Alice_Wong.jpg
│   └── STU002_Bob_Miller/     # Optional: subfolder for multiple photos
├── database/
│   ├── attendance.db           # SQLite database
│   ├── face_encodings_cache.pkl# Fast encodings cache
│   └── captures/               # Timestamped debug frames with bounding boxes
├── config.py                   # Central settings
├── db_manager.py               # SQLite tables & CRUD operations
├── vision.py                   # OpenCV capture & face_recognition embeddings
├── tracker.py                  # 3/6 Interval state machine & summary logic
├── scheduler.py                # 10-minute automated schedule runner
├── main.py                     # Main application entry point
├── register_student.py         # Student registration tool
└── test_system.py              # Automated test suite
```

---

## Quick Start

### 1. Register a Student
You can simply drop images (e.g. `STU001_John_Doe.jpg`) directly into `known_faces/`, or use the interactive registration utility:

- **Capture via Webcam**:
  ```powershell
  .venv\Scripts\python.exe register_student.py --id STU001_John_Doe --name "John Doe"
  ```
  *(Press SPACE to snap, ESC to cancel)*

- **Import existing photo**:
  ```powershell
  .venv\Scripts\python.exe register_student.py --id STU002_Jane_Smith --name "Jane Smith" --from-file "C:\path\to\photo.jpg"
  ```

- **List registered students**:
  ```powershell
  .venv\Scripts\python.exe register_student.py --list
  ```

### 2. Run Autonomous Attendance
```powershell
.venv\Scripts\python.exe main.py
```
*(Runs an immediate snapshot, then runs every 10 minutes continuously. Press `Ctrl+C` to cleanly exit.)*

### 3. Run Simulation Test (30 seconds)
```powershell
.venv\Scripts\python.exe scheduler.py --test
```

### 4. View Attendance History
```powershell
.venv\Scripts\python.exe scheduler.py --history
```
