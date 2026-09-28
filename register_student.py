"""
Student Registration Utility
Easily register student reference photos to the /known_faces directory
either via webcam snapshot or by importing an existing image file.
"""

import argparse
import shutil
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import cv2
import face_recognition

import config
from db_manager import init_db, register_student
from vision import VisionPipeline


def list_registered_students() -> None:
    """Displays all currently registered students in known_faces."""
    pipeline = VisionPipeline()
    students = pipeline.get_registered_student_ids()
    print("\n" + "=" * 60)
    print("CURRENTLY REGISTERED STUDENTS IN /known_faces:")
    print("=" * 60)
    if not students:
        print("  (No student photos registered yet)")
    for i, s_id in enumerate(students, 1):
        print(f"  {i}. {s_id}")
    print("=" * 60 + "\n")


def register_from_webcam(student_id: str, student_name: str = "") -> bool:
    """
    Opens live webcam preview to capture a high-quality student photo.
    Validates face detection before saving.
    """
    student_id = student_id.strip()
    student_name = student_name.strip() or student_id.replace("_", " ")

    print(f"\nOpening webcam to capture photo for: {student_name} (ID: {student_id})")
    print("  Controls:")
    print("    [SPACE] : Capture frame and analyze face")
    print("    [ESC]   : Cancel registration\n")

    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    if not cap.isOpened():
        print(f"[ERROR] Could not open camera index {config.CAMERA_INDEX}.")
        return False

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)

    captured_frame = None

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[ERROR] Failed to grab frame from camera.")
                break

            display_frame = frame.copy()
            cv2.putText(
                display_frame,
                f"Registering: {student_id} | Press SPACE to capture, ESC to cancel",
                (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )

            cv2.imshow(f"Register Student - {student_id}", display_frame)
            key = cv2.waitKey(1) & 0xFF

            if key == 32:  # SPACE bar
                captured_frame = frame.copy()
                break
            elif key == 27:  # ESC key
                print("Registration cancelled.")
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

    if captured_frame is None:
        return False

    # Verify face presence and quality
    rgb = cv2.cvtColor(captured_frame, cv2.COLOR_BGR2RGB)
    faces = face_recognition.face_locations(rgb)

    if len(faces) == 0:
        print("[ERROR] No face detected in captured frame! Please ensure good lighting and face camera directly.")
        return False
    elif len(faces) > 1:
        print(f"[WARNING] Found {len(faces)} faces in frame. Make sure only the student is visible.")
        return False

    # Save to known_faces
    save_path = config.KNOWN_FACES_DIR / f"{student_id}.jpg"
    cv2.imwrite(str(save_path), captured_frame)
    print(f"[OK] Saved reference image to: {save_path}")

    # Register in SQLite database
    init_db()
    register_student(student_id, student_name, str(save_path))

    # Invalidate / reload fast cache
    VisionPipeline(force_reload=True)
    print(f"[SUCCESS] Successfully registered '{student_name}' ({student_id})!\n")
    return True


def register_from_file(image_path_str: str, student_id: str, student_name: str = "") -> bool:
    """
    Imports an existing image file into /known_faces.
    Validates face detection before copying.
    """
    src_path = Path(image_path_str)
    if not src_path.exists():
        print(f"[ERROR] File not found at '{src_path}'")
        return False

    student_id = student_id.strip()
    student_name = student_name.strip() or student_id.replace("_", " ")

    # Verify image has a detectable face
    try:
        img = face_recognition.load_image_file(str(src_path))
        faces = face_recognition.face_locations(img)
        if len(faces) == 0:
            print(f"[ERROR] No face could be detected in '{src_path.name}'.")
            return False
        if len(faces) > 1:
            print(f"[WARNING] Multiple faces ({len(faces)}) found in '{src_path.name}'. Single student photos are recommended.")
    except Exception as e:
        print(f"[ERROR] Error reading image: {e}")
        return False

    dest_filename = f"{student_id}{src_path.suffix.lower()}"
    dest_path = config.KNOWN_FACES_DIR / dest_filename
    shutil.copy2(src_path, dest_path)
    print(f"[OK] Copied image to: {dest_path}")

    # Register in SQLite database
    init_db()
    register_student(student_id, student_name, str(dest_path))

    # Reload encodings
    VisionPipeline(force_reload=True)
    print(f"[SUCCESS] Successfully registered '{student_name}' ({student_id})!\n")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Student Registration for Attendance Camera")
    parser.add_argument("--id", type=str, help="Student ID (e.g. STU001, John_Doe)")
    parser.add_argument("--name", type=str, default="", help="Student Full Name (optional)")
    parser.add_argument("--from-file", type=str, help="Path to an existing image file to register")
    parser.add_argument("--list", action="store_true", help="List all registered students")

    args = parser.parse_args()

    if args.list:
        list_registered_students()
        return

    if not args.id:
        print("Usage examples:")
        print("  1. Capture photo with webcam:")
        print("     python register_student.py --id STU001_John_Doe --name \"John Doe\"")
        print("  2. Import existing photo:")
        print("     python register_student.py --id STU002_Jane_Smith --from-file C:/path/to/photo.jpg")
        print("  3. List registered students:")
        print("     python register_student.py --list")
        sys.exit(1)

    if args.from_file:
        register_from_file(args.from_file, args.id, args.name)
    else:
        register_from_webcam(args.id, args.name)


if __name__ == "__main__":
    main()
