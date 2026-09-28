"""
Vision Pipeline Module
Handles webcam frame capture and face recognition against /known_faces
"""

import logging
import os
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import face_recognition
import numpy as np

import config

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("AttendanceVision")


class VisionPipeline:
    """
    Vision Pipeline responsible for:
    1. Loading and caching known student faces from /known_faces.
    2. Capturing clean single frames from the webcam.
    3. Detecting and recognizing faces using face_recognition embeddings.
    """

    SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

    def __init__(
        self,
        known_faces_dir: Optional[Path] = None,
        tolerance: float = config.FACE_MATCH_TOLERANCE,
        force_reload: bool = False,
    ):
        self.known_faces_dir = known_faces_dir or config.KNOWN_FACES_DIR
        self.tolerance = tolerance
        self.known_encodings: List[np.ndarray] = []
        self.known_student_ids: List[str] = []
        self.cache_file = config.DATABASE_DIR / "face_encodings_cache.pkl"

        self.load_known_faces(force_reload=force_reload)

    def _get_directory_signature(self) -> str:
        """Computes a lightweight signature of the known_faces directory based on mtimes."""
        files = []
        for root, _, filenames in os.walk(self.known_faces_dir):
            for fname in filenames:
                ext = Path(fname).suffix.lower()
                if ext in self.SUPPORTED_EXTENSIONS:
                    fpath = Path(root) / fname
                    files.append(f"{fpath}:{fpath.stat().st_mtime}")
        return "|".join(sorted(files))

    def load_known_faces(self, force_reload: bool = False) -> None:
        """
        Loads face reference images from /known_faces.
        Supports:
          1. Direct image files: known_faces/STU001_John_Doe.jpg -> ID: STU001_John_Doe
          2. Folders per student: known_faces/STU001_John_Doe/1.jpg -> ID: STU001_John_Doe
        Caches encodings on disk for fast startup.
        """
        current_sig = self._get_directory_signature()

        if not force_reload and self.cache_file.exists():
            try:
                with open(self.cache_file, "rb") as f:
                    cache_data = pickle.load(f)
                if cache_data.get("signature") == current_sig:
                    self.known_encodings = cache_data.get("encodings", [])
                    self.known_student_ids = cache_data.get("student_ids", [])
                    logger.info(
                        f"Loaded {len(self.known_student_ids)} known student encodings from fast cache."
                    )
                    return
            except Exception as e:
                logger.warning(f"Failed to read cache file, recomputing encodings: {e}")

        logger.info(f"Scanning '{self.known_faces_dir}' for reference face images...")
        self.known_encodings = []
        self.known_student_ids = []

        if not self.known_faces_dir.exists():
            self.known_faces_dir.mkdir(parents=True, exist_ok=True)

        # 1. Process top-level image files
        for entry in self.known_faces_dir.iterdir():
            if entry.is_file() and entry.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                student_id = entry.stem
                self._encode_image_file(entry, student_id)

            # 2. Process student subdirectories (e.g. known_faces/STU001/face1.jpg)
            elif entry.is_dir():
                student_id = entry.name
                for sub_img in entry.iterdir():
                    if sub_img.is_file() and sub_img.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                        self._encode_image_file(sub_img, student_id)

        # Save cache
        try:
            with open(self.cache_file, "wb") as f:
                pickle.dump(
                    {
                        "signature": current_sig,
                        "encodings": self.known_encodings,
                        "student_ids": self.known_student_ids,
                    },
                    f,
                )
            logger.info(
                f"Successfully cached {len(self.known_student_ids)} encodings to {self.cache_file}"
            )
        except Exception as e:
            logger.warning(f"Could not write encodings cache: {e}")

    def _encode_image_file(self, img_path: Path, student_id: str) -> None:
        """Loads an image file, detects the face, and stores its encoding."""
        try:
            image = face_recognition.load_image_file(str(img_path))
            encodings = face_recognition.face_encodings(image)
            if encodings:
                self.known_encodings.append(encodings[0])
                self.known_student_ids.append(student_id)
                logger.info(f"Registered face for '{student_id}' from {img_path.name}")
            else:
                logger.warning(
                    f"No face detected in '{img_path.name}'. Make sure the face is clearly visible."
                )
        except Exception as e:
            logger.error(f"Error processing image '{img_path}': {e}")

    def capture_single_frame(
        self,
        camera_index: int = config.CAMERA_INDEX,
        warmup_frames: int = config.CAMERA_WARMUP_FRAMES,
    ) -> Optional[np.ndarray]:
        """
        Initializes the webcam, consumes warmup frames for auto-exposure/white balance,
        captures a single crisp frame, and immediately releases the camera hardware.
        """
        # On Windows, DirectShow (CAP_DSHOW) provides rapid initialization
        if os.name == "nt":
            cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(camera_index)
        else:
            cap = cv2.VideoCapture(camera_index)

        if not cap.isOpened():
            logger.error(f"Cannot open webcam (device index {camera_index}).")
            return None

        try:
            # Set target capture resolution
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)

            # Warmup camera sensor (auto-exposure / white-balance stabilization)
            for _ in range(max(1, warmup_frames)):
                ret, _ = cap.read()
                if not ret:
                    break

            # Capture actual frame
            ret, frame = cap.read()
            if not ret or frame is None:
                logger.error("Webcam failed to read a valid frame.")
                return None

            return frame
        finally:
            # Always immediately release camera device
            cap.release()

    def process_frame(
        self,
        frame: np.ndarray,
        save_debug_image: bool = config.SAVE_ANNOTATED_CAPTURES,
        session_id: Optional[str] = None,
        interval_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Processes a BGR OpenCV frame:
        1. Detects face locations and extracts encodings.
        2. Compares encodings against known student faces.
        3. Annotates detections on frame.
        4. Saves debug capture image if enabled.

        Returns:
            {
                "detected_students": {student_id: confidence_score},
                "unrecognized_faces_count": int,
                "total_faces_detected": int,
                "capture_file": Optional[str],
                "annotated_frame": np.ndarray
            }
        """
        if frame is None:
            return {
                "detected_students": {},
                "unrecognized_faces_count": 0,
                "total_faces_detected": 0,
                "capture_file": None,
                "annotated_frame": None,
            }

        # Convert OpenCV BGR to RGB (required by dlib / face_recognition)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect face bounding boxes and calculate 128-d encodings
        face_locations = face_recognition.face_locations(rgb_frame, model=config.FACE_DETECTION_MODEL)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        detected_students: Dict[str, float] = {}
        unrecognized_count = 0
        annotated_frame = frame.copy()

        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            name = "Unknown"
            confidence = 0.0
            color = (0, 0, 255)  # Red for unknown

            if self.known_encodings:
                distances = face_recognition.face_distance(self.known_encodings, face_encoding)
                best_match_idx = int(np.argmin(distances))
                min_distance = distances[best_match_idx]

                if min_distance <= self.tolerance:
                    student_id = self.known_student_ids[best_match_idx]
                    confidence = round(float(1.0 - min_distance), 3)
                    detected_students[student_id] = confidence
                    name = f"{student_id} ({int(confidence * 100)}%)"
                    color = (0, 255, 0)  # Green for recognized
                else:
                    unrecognized_count += 1
            else:
                unrecognized_count += 1

            # Draw visual bounding box and label
            cv2.rectangle(annotated_frame, (left, top), (right, bottom), color, 2)
            cv2.rectangle(
                annotated_frame,
                (left, bottom - 25),
                (right, bottom),
                color,
                cv2.FILLED,
            )
            cv2.putText(
                annotated_frame,
                name,
                (left + 6, bottom - 6),
                cv2.FONT_HERSHEY_DUPLEX,
                0.55,
                (255, 255, 255),
                1,
            )

        # Add timestamp watermark to image
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            annotated_frame,
            f"AttendanceCam - {timestamp_str}",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2,
        )

        capture_file = None
        if save_debug_image:
            sess_prefix = session_id or "session"
            int_prefix = f"int_{interval_index}" if interval_index is not None else "manual"
            filename = f"{sess_prefix}_{int_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            capture_path = config.CAPTURES_DIR / filename
            cv2.imwrite(str(capture_path), annotated_frame)
            capture_file = str(capture_path)

        return {
            "detected_students": detected_students,
            "unrecognized_faces_count": unrecognized_count,
            "total_faces_detected": len(face_locations),
            "capture_file": capture_file,
            "annotated_frame": annotated_frame,
        }

    def capture_and_identify(
        self,
        session_id: Optional[str] = None,
        interval_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """High-level single call: capture single frame and identify all faces."""
        frame = self.capture_single_frame()
        if frame is None:
            logger.warning("Frame capture returned None. No faces could be processed.")
            return {
                "detected_students": {},
                "unrecognized_faces_count": 0,
                "total_faces_detected": 0,
                "capture_file": None,
                "annotated_frame": None,
            }
        return self.process_frame(
            frame,
            save_debug_image=config.SAVE_ANNOTATED_CAPTURES,
            session_id=session_id,
            interval_index=interval_index,
        )

    def get_registered_student_ids(self) -> List[str]:
        """Returns unique list of registered student IDs from known faces."""
        return sorted(list(set(self.known_student_ids)))
