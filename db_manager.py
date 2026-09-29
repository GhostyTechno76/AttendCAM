"""
SQLite Database Management Module for Autonomous Attendance System
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import config


_db_initialized = False


def get_db_connection() -> sqlite3.Connection:
    """Creates and returns a connection to SQLite with row factory enabled."""
    ensure_db()
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initializes the database schema if tables do not exist."""
    global _db_initialized
    conn = sqlite3.connect(str(config.DB_PATH))
    with conn:
        cursor = conn.cursor()

        # Students Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                image_path TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Interval Detections Table (Every 10-minute snapshot)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS interval_detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                interval_index INTEGER NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                student_id TEXT NOT NULL,
                detected INTEGER NOT NULL,  -- 1 = Yes, 0 = No
                confidence REAL,
                capture_file TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
            """
        )

        # Hourly Attendance Final Summary Table (After 6 intervals)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS hourly_attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                session_start TIMESTAMP NOT NULL,
                session_end TIMESTAMP NOT NULL,
                student_id TEXT NOT NULL,
                detection_count INTEGER NOT NULL,
                total_intervals INTEGER NOT NULL,
                status TEXT NOT NULL,  -- 'Present' or 'Absent'
                marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
            """
        )

        conn.commit()
    _db_initialized = True


def ensure_db() -> None:
    """Ensures database tables are created at least once."""
    global _db_initialized
    if not _db_initialized:
        init_db()


def register_student(student_id: str, name: str, image_path: Optional[str] = None) -> None:
    """Inserts or updates a student in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO students (student_id, name, image_path)
            VALUES (?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                name=excluded.name,
                image_path=coalesce(excluded.image_path, students.image_path)
            """,
            (student_id, name, image_path),
        )
        conn.commit()


def sync_known_students(student_ids: List[str]) -> None:
    """Ensures all student IDs found in known_faces exist in the students table."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for s_id in student_ids:
            # Human-readable name from student_id (e.g. 'STU001_John_Doe' -> 'John Doe')
            display_name = s_id.replace("_", " ")
            cursor.execute(
                """
                INSERT OR IGNORE INTO students (student_id, name)
                VALUES (?, ?)
                """,
                (s_id, display_name),
            )
        conn.commit()


def record_interval_results(
    session_id: str,
    interval_index: int,
    all_students: List[str],
    detected_students: Dict[str, float],
    capture_file: Optional[str] = None,
) -> None:
    """
    Logs detection status for every registered student for a given interval.
    
    detected_students: dict mapping student_id -> confidence_score (or 1.0 - distance)
    """
    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for s_id in all_students:
            is_detected = 1 if s_id in detected_students else 0
            conf = detected_students.get(s_id, 0.0)
            cursor.execute(
                """
                INSERT INTO interval_detections
                (session_id, interval_index, timestamp, student_id, detected, confidence, capture_file)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, interval_index, now, s_id, is_detected, conf, capture_file),
            )
        conn.commit()


def record_hourly_summary(
    session_id: str,
    session_start: str,
    session_end: str,
    summary_data: List[Dict[str, Any]],
) -> None:
    """
    Records the final Present / Absent statuses for an hourly session.
    summary_data items: {
        'student_id': str,
        'detection_count': int,
        'total_intervals': int,
        'status': 'Present' | 'Absent'
    }
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for item in summary_data:
            cursor.execute(
                """
                INSERT INTO hourly_attendance
                (session_id, session_start, session_end, student_id, detection_count, total_intervals, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    session_start,
                    session_end,
                    item["student_id"],
                    item["detection_count"],
                    item["total_intervals"],
                    item["status"],
                ),
            )
        conn.commit()


def get_latest_hourly_summaries(limit: int = 20) -> List[Dict[str, Any]]:
    """Returns the most recent hourly attendance summary entries."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT h.id, h.session_id, h.session_start, h.session_end,
                   h.student_id, s.name, h.detection_count, h.total_intervals,
                   h.status, h.marked_at
            FROM hourly_attendance h
            LEFT JOIN students s ON h.student_id = s.student_id
            ORDER BY h.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_session_interval_details(session_id: str) -> List[Dict[str, Any]]:
    """Returns interval breakdown for a specific session."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT interval_index, timestamp, student_id, detected, confidence, capture_file
            FROM interval_detections
            WHERE session_id = ?
            ORDER BY interval_index ASC, student_id ASC
            """,
            (session_id,),
        )
        return [dict(row) for row in cursor.fetchall()]
