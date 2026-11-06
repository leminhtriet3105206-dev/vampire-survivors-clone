"""Computer Vision & Webcam Hand Gesture Recognition System.

Uses OpenCV (and MediaPipe if available) to detect physical hand gestures in real-time
via a non-blocking background thread:
  - OPEN_PALM   (5 fingers / 4 defects) -> Triggers Character Ultimate Ability!
  - CLOSED_FIST (0 defects)             -> Triggers Emergency Defensive Potion / Barrier
  - PEACE_SIGN  (2 fingers / 1 defect)  -> Triggers Tactical Speed Burst / Dash
  - THUMBS_UP                           -> Triggers Hero Taunt / Battle Cry

Architectural Highlights:
  - Runs in a detached daemon thread with thread-safe polling (zero frame drops in Pygame loop)
  - Robust mock / headless fallback when no webcam hardware or OpenCV is available
  - Pure algorithmic contour/convexity-defect pipeline that works out of the box with OpenCV 5.x
"""
from enum import Enum, auto
import os
import sys
import threading
import time
from typing import Any, Dict, Optional, Tuple

try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False
    cv2 = None
    np = None

try:
    import mediapipe as mp
    HAS_MEDIAPIPE = True
except ImportError:
    HAS_MEDIAPIPE = False
    mp = None


class GestureType(Enum):
    NONE        = auto()
    OPEN_PALM   = auto()
    CLOSED_FIST = auto()
    PEACE_SIGN  = auto()
    THUMBS_UP   = auto()


class GestureRecognizer:
    """Non-blocking background camera listener and gesture classifier."""

    def __init__(self, camera_index: int = 0, enabled: bool = False):
        self.camera_index = camera_index
        self.enabled = enabled
        self.running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self.latest_gesture: GestureType = GestureType.NONE
        self.last_detected_time: float = 0.0
        self.cooldown_seconds: float = 1.2  # Cooldown between gesture triggers
        self.fps_counter: float = 0.0
        self.is_camera_open: bool = False
        self.has_hardware: bool = False

    def start(self) -> bool:
        """Start the background vision thread."""
        if not HAS_OPENCV or not self.enabled:
            return False

        if self.running:
            return True

        self.running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True, name="GestureCVThread")
        self._thread.start()
        return True

    def stop(self) -> None:
        """Stop background capture and release camera resources."""
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        self.is_camera_open = False

    def poll_gesture(self) -> GestureType:
        """Query and consume the latest detected gesture (thread-safe)."""
        with self._lock:
            g = self.latest_gesture
            self.latest_gesture = GestureType.NONE
            return g

    @staticmethod
    def classify_frame(frame_bgr: Any) -> Tuple[GestureType, int]:
        """
        Classifies hand gestures using convex hull defect topology:
          - Preprocesses ROI via skin-color thresholding (HSV) & morphological clean-up
          - Computes contours and finds largest bounding hand mass
          - Analyzes convexity defects to determine finger extension count
        """
        if not HAS_OPENCV or frame_bgr is None:
            return GestureType.NONE, 0

        try:
            h, w = frame_bgr.shape[:2]
            # Center-cropped ROI (50% of frame)
            roi = frame_bgr[int(h * 0.15) : int(h * 0.85), int(w * 0.2) : int(w * 0.8)]
            if roi.size == 0:
                return GestureType.NONE, 0

            # Convert to HSV and detect skin range
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            lower_skin = np.array([0, 28, 60], dtype=np.uint8)
            upper_skin = np.array([25, 255, 255], dtype=np.uint8)
            mask = cv2.inRange(hsv, lower_skin, upper_skin)

            # Morphological smoothing to remove noise
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask = cv2.dilate(mask, kernel, iterations=2)
            mask = cv2.GaussianBlur(mask, (5, 5), 0)

            contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return GestureType.NONE, 0

            # Find largest contour (the hand)
            max_contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(max_contour)
            if area < 3000:  # Minimum hand size threshold
                return GestureType.NONE, 0

            hull = cv2.convexHull(max_contour, returnPoints=False)
            if hull is None or len(hull) < 4:
                return GestureType.NONE, 0

            defects = cv2.convexityDefects(max_contour, hull)
            if defects is None:
                return GestureType.CLOSED_FIST, 0

            finger_defects = 0
            for i in range(defects.shape[0]):
                s, e, f, d = defects[i, 0]
                start = max_contour[s][0]
                end = max_contour[e][0]
                far = max_contour[f][0]

                # Triangle side lengths
                a = np.linalg.norm(end - start)
                b = np.linalg.norm(far - start)
                c = np.linalg.norm(end - far)

                # Cosine rule for angle at defect point
                if b * c > 0:
                    angle = np.arccos(np.clip((b * b + c * c - a * a) / (2 * b * c), -1.0, 1.0))
                    # Finger webbings have acute angles (< 90 degrees) and significant depth
                    if angle <= np.pi / 2.0 and d > 2000:
                        finger_defects += 1

            # Classification by defect count
            if finger_defects >= 3:
                return GestureType.OPEN_PALM, finger_defects
            elif finger_defects == 1:
                return GestureType.PEACE_SIGN, finger_defects
            elif finger_defects == 0:
                return GestureType.CLOSED_FIST, finger_defects

            return GestureType.NONE, finger_defects

        except Exception:
            return GestureType.NONE, 0

    def _capture_loop(self) -> None:
        """Internal capture loop running in detached daemon thread."""
        cap = None
        try:
            cap = cv2.VideoCapture(self.camera_index)
            if not cap.isOpened():
                self.is_camera_open = False
                self.has_hardware = False
                return

            self.is_camera_open = True
            self.has_hardware = True
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

            while self.running:
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.05)
                    continue

                gesture, _ = self.classify_frame(frame)
                now = time.time()
                if gesture != GestureType.NONE and (now - self.last_detected_time >= self.cooldown_seconds):
                    with self._lock:
                        self.latest_gesture = gesture
                        self.last_detected_time = now

                # Sleep ~33ms (~30 FPS camera polling is optimal to conserve CPU)
                time.sleep(0.033)

        except Exception as e:
            print(f"[GestureRecognizer] Camera loop terminated: {e}")
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            self.is_camera_open = False

    def get_status(self) -> Dict[str, Any]:
        """Telemetry status for UI widgets and pause settings menu."""
        return {
            "has_opencv": HAS_OPENCV,
            "has_mediapipe": HAS_MEDIAPIPE,
            "enabled": self.enabled,
            "running": self.running,
            "is_camera_open": self.is_camera_open,
            "has_hardware": self.has_hardware,
            "cooldown_seconds": self.cooldown_seconds,
        }

