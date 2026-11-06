"""Unit Tests for Phase 4: Computer Vision & Hand Gesture Recognition.

Validates:
  1. GestureRecognizer lifecycle (initialization, start, stop, telemetry)
  2. Thread-safe poll_gesture consumption
  3. Frame classification robustness against null / noisy / synthetic frames
  4. Graceful headless degradation without physical webcam hardware
"""
import os
import sys
import unittest

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from systems.gesture_recognition import GestureRecognizer, GestureType, HAS_OPENCV

if HAS_OPENCV:
    import numpy as np


class GestureRecognitionTests(unittest.TestCase):
    def setUp(self):
        self.recognizer = GestureRecognizer(camera_index=999, enabled=False)

    def tearDown(self):
        self.recognizer.stop()

    def test_initial_state_and_telemetry(self):
        status = self.recognizer.get_status()
        self.assertFalse(status["enabled"])
        self.assertFalse(status["running"])
        self.assertFalse(status["is_camera_open"])
        self.assertEqual(self.recognizer.poll_gesture(), GestureType.NONE)

    def test_thread_safe_polling_and_consumption(self):
        with self.recognizer._lock:
            self.recognizer.latest_gesture = GestureType.OPEN_PALM

        # First poll retrieves OPEN_PALM
        first_poll = self.recognizer.poll_gesture()
        self.assertEqual(first_poll, GestureType.OPEN_PALM)

        # Subsequent poll returns NONE (consumed)
        second_poll = self.recognizer.poll_gesture()
        self.assertEqual(second_poll, GestureType.NONE)

    def test_classify_frame_with_empty_or_black_frame(self):
        if not HAS_OPENCV:
            self.skipTest("OpenCV not installed in this environment")

        # Null frame
        g_null, _ = GestureRecognizer.classify_frame(None)
        self.assertEqual(g_null, GestureType.NONE)

        # Empty/Black frame
        black_frame = np.zeros((240, 320, 3), dtype=np.uint8)
        g_black, _ = GestureRecognizer.classify_frame(black_frame)
        self.assertEqual(g_black, GestureType.NONE)

    def test_start_and_stop_lifecycle_without_hardware(self):
        # Even with invalid camera index (999), it should not raise exceptions
        self.recognizer.enabled = True
        started = self.recognizer.start()
        # Thread starts, detects no hardware, and gracefully marks is_camera_open as False
        self.assertTrue(started)
        self.recognizer.stop()
        self.assertFalse(self.recognizer.running)


if __name__ == "__main__":
    unittest.main()

