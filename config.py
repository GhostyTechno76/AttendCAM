"""
Configuration settings for Autonomous Attendance Camera System
"""

import sys
from pathlib import Path

# Base Paths
if getattr(sys, "frozen", False):
    # Running as compiled PyInstaller executable (e.g. AttendCamBeta.exe)
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

KNOWN_FACES_DIR = BASE_DIR / "known_faces"
DATABASE_DIR = BASE_DIR / "database"
DB_PATH = DATABASE_DIR / "attendance.db"
CAPTURES_DIR = DATABASE_DIR / "captures"

# Ensure runtime directories exist
KNOWN_FACES_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)

# Camera Settings
CAMERA_INDEX = 0             # Default webcam index
CAMERA_WARMUP_FRAMES = 5     # Frames to discard for auto-exposure stabilization
CAMERA_WIDTH = 1280          # Requested capture width
CAMERA_HEIGHT = 720          # Requested capture height

# Face Recognition Settings
# Lower tolerance = more strict (fewer false positives).
# 0.6 is the default for dlib/face_recognition; 0.55 offers higher precision.
FACE_MATCH_TOLERANCE = 0.55
FACE_DETECTION_MODEL = "hog"  # 'hog' is fast on CPU; 'cnn' for GPU if CUDA available
SAVE_ANNOTATED_CAPTURES = True

# 3/6 Attendance Interval Rules
INTERVAL_MINUTES = 10                  # Interval between captures (minutes)
TOTAL_INTERVALS_PER_SESSION = 6        # 6 intervals = 1 hour session
REQUIRED_DETECTIONS_FOR_PRESENT = 3    # If detected in >= 3 intervals -> Present, else Absent
