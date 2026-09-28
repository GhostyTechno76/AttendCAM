"""
Automated Test Suite for Attendance Camera System
Tests:
1. Database creation, tables, interval logging, and hourly summary.
2. 3/6 Interval Tracker logic (verification of Present >= 3 and Absent < 3).
3. Session counter reset functionality.
4. Camera single frame capture test.
"""

import os
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock

import config
import db_manager
from tracker import AttendanceTracker
from vision import VisionPipeline


class TestAttendanceSystem(unittest.TestCase):

    def setUp(self):
        # Initialize DB
        db_manager.init_db()

    def test_01_db_initialization(self):
        """Verify database connection and schema tables."""
        conn = db_manager.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row["name"] for row in cursor.fetchall()]
        conn.close()

        self.assertIn("students", tables)
        self.assertIn("interval_detections", tables)
        self.assertIn("hourly_attendance", tables)

    def test_02_tracker_logic_three_six_rule(self):
        """
        Verify the 3/6 interval rule:
        - 6 intervals simulated
        - Student Alice: detected 4 times (>= 3) -> Present
        - Student Bob: detected 2 times (< 3)   -> Absent
        - Student Charlie: detected 5 times (>=3) -> Present
        - Student Dave: detected 0 times (< 3)  -> Absent
        """
        # Mock VisionPipeline so we can deterministically test the 3/6 tracker logic
        mock_vision = MagicMock(spec=VisionPipeline)
        mock_vision.get_registered_student_ids.return_value = [
            "STU001_Alice",
            "STU002_Bob",
            "STU003_Charlie",
            "STU004_Dave",
        ]

        tracker = AttendanceTracker(vision_pipeline=mock_vision)

        # Pre-planned detections for 6 intervals:
        # Interval 1: Alice, Charlie
        # Interval 2: Alice, Bob, Charlie
        # Interval 3: Charlie
        # Interval 4: Alice, Charlie
        # Interval 5: Bob, Charlie
        # Interval 6: Alice
        interval_detections = [
            {"STU001_Alice": 0.85, "STU003_Charlie": 0.90},
            {"STU001_Alice": 0.82, "STU002_Bob": 0.78, "STU003_Charlie": 0.88},
            {"STU003_Charlie": 0.92},
            {"STU001_Alice": 0.86, "STU003_Charlie": 0.89},
            {"STU002_Bob": 0.80, "STU003_Charlie": 0.91},
            {"STU001_Alice": 0.84},
        ]

        summary_result = None

        for idx, det in enumerate(interval_detections, 1):
            mock_vision.capture_and_identify.return_value = {
                "detected_students": det,
                "unrecognized_faces_count": 0,
                "total_faces_detected": len(det),
                "capture_file": None,
                "annotated_frame": None,
            }
            res = tracker.run_interval_capture()
            if idx == 6:
                self.assertEqual(res["status"], "session_completed")
                summary_result = res["summary"]
            else:
                self.assertEqual(res["status"], "interval_completed")

        self.assertIsNotNone(summary_result)
        summary_dict = {item["student_id"]: item for item in summary_result}

        # Verify Alice: 4 detections -> Present
        self.assertEqual(summary_dict["STU001_Alice"]["detection_count"], 4)
        self.assertEqual(summary_dict["STU001_Alice"]["status"], "Present")

        # Verify Bob: 2 detections -> Absent
        self.assertEqual(summary_dict["STU002_Bob"]["detection_count"], 2)
        self.assertEqual(summary_dict["STU002_Bob"]["status"], "Absent")

        # Verify Charlie: 5 detections -> Present
        self.assertEqual(summary_dict["STU003_Charlie"]["detection_count"], 5)
        self.assertEqual(summary_dict["STU003_Charlie"]["status"], "Present")

        # Verify Dave: 0 detections -> Absent
        self.assertEqual(summary_dict["STU004_Dave"]["detection_count"], 0)
        self.assertEqual(summary_dict["STU004_Dave"]["status"], "Absent")

        # Verify counters were reset for the subsequent session
        self.assertEqual(tracker.current_interval, 0)
        for s_id in mock_vision.get_registered_student_ids():
            self.assertEqual(tracker.detection_counts[s_id], 0)

    def test_03_camera_capture_probe(self):
        """Verifies physical webcam frame capture."""
        pipeline = VisionPipeline()
        frame = pipeline.capture_single_frame()
        self.assertIsNotNone(frame, "Webcam capture failed to produce a valid frame.")
        self.assertEqual(len(frame.shape), 3, "Frame must have 3 channels (H, W, C).")
        self.assertEqual(frame.shape[2], 3, "Frame must be 3-channel color image.")


if __name__ == "__main__":
    unittest.main()
