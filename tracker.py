"""
Attendance Tracker Module (3/6 Interval Rule)
Manages the 10-minute snapshot intervals, detection counters, and hourly summary evaluations.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import config
import db_manager
from vision import VisionPipeline

logger = logging.getLogger("AttendanceTracker")


class AttendanceTracker:
    """
    Implements the 3/6 Interval Attendance Tracker:
    - Executes every 10 minutes (6 intervals per 1-hour session).
    - Maintains in-memory dictionary and SQLite logs of student detection counts.
    - At interval 6 (1 hour), marks status = 'Present' if detection_count >= 3, else 'Absent'.
    - Resets session counters for the subsequent hour.
    """

    def __init__(self, vision_pipeline: Optional[VisionPipeline] = None):
        self.vision = vision_pipeline or VisionPipeline()
        self.total_intervals = config.TOTAL_INTERVALS_PER_SESSION
        self.required_detections = config.REQUIRED_DETECTIONS_FOR_PRESENT
        
        # Ensure database tables exist
        db_manager.init_db()

        # Session state
        self.session_id: str = ""
        self.session_start_time: datetime = datetime.now()
        self.current_interval: int = 0
        self.detection_counts: Dict[str, int] = {}
        
        self.start_new_session()

    def start_new_session(self) -> None:
        """Initializes a new 1-hour session and resets interval counters."""
        self.session_start_time = datetime.now()
        self.session_id = f"SESS_{self.session_start_time.strftime('%Y%m%d_%H%M%S')}"
        self.current_interval = 0

        # Reload/sync registered students
        registered_students = self.vision.get_registered_student_ids()
        db_manager.sync_known_students(registered_students)

        # In-memory dictionary tracking student_id -> detection_count
        self.detection_counts = {student_id: 0 for student_id in registered_students}

        logger.info(
            f"=== Started New Attendance Session: {self.session_id} ==="
        )
        logger.info(
            f"Registered students loaded ({len(registered_students)}): {registered_students or 'None (add images to /known_faces)'}"
        )
        logger.info(
            f"Rule: Must be detected in >= {self.required_detections}/{self.total_intervals} intervals to be marked 'Present'."
        )

    def run_interval_capture(self) -> Dict[str, Any]:
        """
        Executes a single interval snapshot:
        1. Increments interval index (1 to 6).
        2. Captures single frame and identifies faces.
        3. Updates in-memory detection dictionary.
        4. Logs interval record to SQLite.
        5. If interval 6 is reached, evaluates hourly attendance and resets.
        """
        self.current_interval += 1
        interval_start = datetime.now()

        logger.info(
            f"--- Starting Interval [{self.current_interval}/{self.total_intervals}] "
            f"at {interval_start.strftime('%H:%M:%S')} ---"
        )

        # Perform single camera frame capture & recognition
        result = self.vision.capture_and_identify(
            session_id=self.session_id,
            interval_index=self.current_interval,
        )

        detected_map = result.get("detected_students", {})
        all_registered = self.vision.get_registered_student_ids()

        # Ensure all registered students exist in our dictionary
        for s_id in all_registered:
            if s_id not in self.detection_counts:
                self.detection_counts[s_id] = 0

        # Update in-memory dictionary counter
        detected_names = []
        for s_id in detected_map:
            self.detection_counts[s_id] = self.detection_counts.get(s_id, 0) + 1
            conf = detected_map[s_id]
            detected_names.append(f"{s_id} ({int(conf * 100)}%)")

        # Persist interval log to SQLite table
        db_manager.record_interval_results(
            session_id=self.session_id,
            interval_index=self.current_interval,
            all_students=all_registered,
            detected_students=detected_map,
            capture_file=result.get("capture_file"),
        )

        # Interval Log Output
        logger.info(
            f"Interval [{self.current_interval}/{self.total_intervals}] Completed. "
            f"Detected ({len(detected_map)}): {detected_names or 'None'} | "
            f"Unrecognized faces: {result.get('unrecognized_faces_count', 0)}"
        )
        self._print_current_counts_table()

        # Check if 1-hour session (6 intervals) has finished
        if self.current_interval >= self.total_intervals:
            logger.info(f"Reached final interval ({self.total_intervals}/{self.total_intervals}). Finalizing 1-hour session...")
            summary = self.evaluate_and_summarize()
            self.start_new_session()  # Reset for next hour
            return {"status": "session_completed", "interval": self.current_interval, "summary": summary}

        return {"status": "interval_completed", "interval": self.current_interval, "detected": detected_map}

    def evaluate_and_summarize(self) -> List[Dict[str, Any]]:
        """
        Summary function executed after 6 intervals (1 hour):
        - If detection_count >= 3 -> 'Present'
        - Else -> 'Absent'
        - Stores final results in SQLite hourly_attendance table.
        - Prints detailed session report.
        """
        session_end = datetime.now()
        start_str = self.session_start_time.isoformat()
        end_str = session_end.isoformat()

        summary_records: List[Dict[str, Any]] = []
        all_registered = sorted(list(self.detection_counts.keys()))

        for student_id in all_registered:
            count = self.detection_counts.get(student_id, 0)
            status = "Present" if count >= self.required_detections else "Absent"
            summary_records.append(
                {
                    "student_id": student_id,
                    "detection_count": count,
                    "total_intervals": self.total_intervals,
                    "status": status,
                }
            )

        # Save to SQLite database
        db_manager.record_hourly_summary(
            session_id=self.session_id,
            session_start=start_str,
            session_end=end_str,
            summary_data=summary_records,
        )

        # Print formatted summary table to console
        self._print_summary_report(summary_records, self.session_start_time, session_end)

        return summary_records

    def _print_current_counts_table(self) -> None:
        """Helper to print a compact live interval status table."""
        if not self.detection_counts:
            return
        header = f"{'Student ID':<25} | {'Detections So Far':<20} | {'Status Trend'}"
        sep = "-" * len(header)
        lines = [sep, header, sep]
        for s_id, count in sorted(self.detection_counts.items()):
            trend = "Likely Present" if count >= self.required_detections else f"Needs {self.required_detections - count} more"
            lines.append(f"{s_id:<25} | {f'{count}/{self.current_interval}':<20} | {trend}")
        lines.append(sep)
        print("\n" + "\n".join(lines) + "\n")

    def _print_summary_report(
        self,
        summary: List[Dict[str, Any]],
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """Prints a prominent ASCII table of the final hourly attendance decision."""
        title = f"HOURLY ATTENDANCE REPORT: {self.session_id}"
        time_info = (
            f"Period: {start_time.strftime('%Y-%m-%d %H:%M:%S')} to {end_time.strftime('%H:%M:%S')} "
            f"({self.total_intervals} Intervals of 10 min)"
        )
        sep = "=" * 80
        header = f"{'Student ID':<28} | {'Detections':<15} | {'Requirement':<15} | {'Final Status'}"
        sub_sep = "-" * 80

        lines = ["\n" + sep, f"  {title}", f"  {time_info}", sep, header, sub_sep]

        present_count = 0
        absent_count = 0

        for rec in summary:
            s_id = rec["student_id"]
            count = rec["detection_count"]
            status = rec["status"]
            req = f">={self.required_detections}/{self.total_intervals}"
            status_display = f"[ {status.upper()} ]"
            if status == "Present":
                present_count += 1
            else:
                absent_count += 1
            lines.append(f"{s_id:<28} | {f'{count}/{self.total_intervals}':<15} | {req:<15} | {status_display}")

        lines.append(sub_sep)
        lines.append(f"Summary: Present: {present_count} | Absent: {absent_count} | Total Registered: {len(summary)}")
        lines.append(sep + "\n")
        print("\n".join(lines))
