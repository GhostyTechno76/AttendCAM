"""
Autonomous Attendance Scheduler
Executes the attendance interval capture exactly every 10 minutes using `schedule`.
"""

import argparse
import logging
import sys
import time
from datetime import datetime

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import schedule

import config
import db_manager
from tracker import AttendanceTracker
from vision import VisionPipeline

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("Scheduler")


def run_scheduler(interval_minutes: int = config.INTERVAL_MINUTES, run_on_start: bool = True) -> None:
    """
    Standard production scheduler:
    Configures `schedule` to run interval capture every 10 minutes.
    """
    logger.info("Initializing Autonomous Attendance Camera System...")
    vision = VisionPipeline()
    tracker = AttendanceTracker(vision_pipeline=vision)

    registered_students = vision.get_registered_student_ids()
    if not registered_students:
        logger.warning(
            "[!] No student photos found in /known_faces! "
            "Please add reference photos (e.g. known_faces/STU001_John.jpg) "
            "or use `python register_student.py`."
        )

    # Schedule task every interval_minutes
    schedule.every(interval_minutes).minutes.do(tracker.run_interval_capture)
    logger.info(f"[OK] Scheduler configured: Capturing webcam frame every {interval_minutes} minutes.")
    logger.info(f"Target cycle: 6 intervals (1 hour). Rule: >= 3 detections = Present.")

    # Execute first capture immediately on startup if requested
    if run_on_start:
        logger.info("[START] Triggering initial Interval [1/6] immediately on startup...")
        tracker.run_interval_capture()

    logger.info(f"Scheduler is active. Waiting for next interval ({interval_minutes}m)... Press Ctrl+C to exit.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n[EXIT] Attendance camera stopped by user (Ctrl+C). Exiting cleanly.")


def run_fast_test(interval_seconds: int = 5, total_intervals: int = 6) -> None:
    """
    Simulation / verification mode:
    Runs a complete 6-interval test with a short delay (e.g. 5 seconds)
    to verify the full pipeline and SQLite summary logging in under a minute.
    """
    logger.info(f"[TEST] Running fast test mode: {total_intervals} intervals with {interval_seconds}s delay...")
    vision = VisionPipeline()
    tracker = AttendanceTracker(vision_pipeline=vision)

    for i in range(1, total_intervals + 1):
        tracker.run_interval_capture()
        if i < total_intervals:
            logger.info(f"Sleeping {interval_seconds} seconds before next test interval...")
            time.sleep(interval_seconds)

    logger.info("[SUCCESS] Fast test completed successfully. Check database/attendance.db for saved logs.")


def show_attendance_history(limit: int = 20) -> None:
    """Displays latest records stored in the SQLite database."""
    records = db_manager.get_latest_hourly_summaries(limit=limit)
    if not records:
        print("\nNo attendance records found in SQLite database yet.")
        return

    print("\n" + "=" * 90)
    print(f"{'ID':<4} | {'Session ID':<24} | {'Student ID':<20} | {'Detections':<12} | {'Status':<10} | {'Marked At'}")
    print("-" * 90)
    for r in records:
        det_ratio = f"{r['detection_count']}/{r['total_intervals']}"
        print(
            f"{r['id']:<4} | {r['session_id']:<24} | {r['student_id']:<20} | "
            f"{det_ratio:<12} | "
            f"{r['status']:<10} | {r['marked_at']}"
        )
    print("=" * 90 + "\n")


def capture_now_test() -> None:
    """Triggers an on-demand single capture to verify camera and face detection."""
    logger.info("Capturing single on-demand test frame...")
    vision = VisionPipeline()
    result = vision.capture_and_identify()

    print("\n" + "=" * 50)
    print("SINGLE CAPTURE DIAGNOSTIC RESULT:")
    print("=" * 50)
    print(f"Total Faces Detected: {result['total_faces_detected']}")
    print(f"Recognized Students : {list(result['detected_students'].keys()) or 'None'}")
    for s_id, conf in result["detected_students"].items():
        print(f"  - {s_id}: Match Confidence = {int(conf * 100)}%")
    print(f"Unrecognized Faces  : {result['unrecognized_faces_count']}")
    if result.get("capture_file"):
        print(f"Annotated snapshot  : {result['capture_file']}")
    print("=" * 50 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous Attendance Camera System")
    parser.add_argument(
        "--interval",
        type=int,
        default=config.INTERVAL_MINUTES,
        help="Interval in minutes between webcam snapshots (default: 10)",
    )
    parser.add_argument(
        "--no-startup-capture",
        action="store_true",
        help="Do not take an immediate capture on launch; wait for the first 10-minute timer",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run a 6-interval test simulation with 5-second intervals to verify the full cycle",
    )
    parser.add_argument(
        "--capture-now",
        action="store_true",
        help="Take a single test snapshot right now and display detected faces",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="View recent hourly attendance records from SQLite",
    )

    args = parser.parse_args()

    if args.history:
        show_attendance_history()
    elif args.capture_now:
        capture_now_test()
    elif args.test:
        run_fast_test(interval_seconds=5)
    else:
        run_scheduler(
            interval_minutes=args.interval,
            run_on_start=not args.no_startup_capture,
        )


if __name__ == "__main__":
    main()
