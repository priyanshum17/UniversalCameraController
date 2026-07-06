import logging
import subprocess
import re
import sys
import os
from typing import Callable, Optional, List, Dict, Any
from src.camera_app.services.config_service import ConfigService
from src.camera_app.services.camera_service import CameraService
from src.camera_app.services.upload_service import UploadService

logger = logging.getLogger(__name__)


class AppController:
    """
    The Brain of the application. Orchestrates all underlying services
    and encapsulates business logic.

    The View (UI) calls methods on this controller, and the controller
    manages the state and interacts with services.
    """

    def __init__(self) -> None:
        """Initializes the controller and all dependent services."""
        self.config_service: ConfigService = ConfigService()

        # Run device auto-detection on startup (gathers all physical devices)
        self.detected_cameras: List[Dict[str, str]] = self.detect_cameras()

        self.upload_service: UploadService = UploadService()
        self.camera_service: CameraService = CameraService(self.config_service)

        # State
        # Load active camera config from settings (default to first detected if empty)
        self.active_camera_config: Optional[Dict[str, Any]] = self.config_service.get(
            "active_camera"
        )
        if not self.active_camera_config and self.detected_cameras:
            first_cam = self.detected_cameras[0]
            self.active_camera_config = {
                "id": "active_cam",
                "name": first_cam["name"],
                "device": first_cam["device"],
                "fps": 30,
                "resolution": "640x480",
            }
            self.config_service.set("active_camera", self.active_camera_config)

        self.is_recording: bool = False
        self._on_frame_callback: Optional[Callable[[str, bytes, int, int], None]] = None

        self.upload_service.start()

    def set_frame_callback(
        self, callback: Callable[[str, bytes, int, int], None]
    ) -> None:
        """
        Registers a callback to receive video frames and starts preview mode.

        Args:
            callback (Callable): The function to call when a frame is ready.
        """
        self._on_frame_callback = callback
        self.start_preview()

    def select_camera(self, name: str, device: str) -> None:
        """
        Switches the active camera feed to the chosen hardware device.

        Args:
            name (str): The display name of the camera.
            device (str): The hardware device index or node path.
        """
        if self.active_camera_config and self.active_camera_config["device"] == device:
            return

        logger.info(f"AppController: Switching selected camera to {name} ({device})")

        if self.is_recording:
            self.stop_recording()
            self._update_active_config(name, device)
            self.start_recording()
        else:
            self.stop_preview()
            self._update_active_config(name, device)
            self.start_preview()

    def _update_active_config(self, name: str, device: str) -> None:
        """Updates and persists the active camera config settings."""
        self.active_camera_config = {
            "id": "active_cam",
            "name": name,
            "device": device,
            "fps": 30,
            "resolution": "640x480",
        }
        self.config_service.set("active_camera", self.active_camera_config)

    def start_preview(self) -> None:
        """Starts preview mode (no disk write, 10fps stream to UI) for the selected camera."""
        if self.is_recording or not self.active_camera_config:
            return
        logger.info(
            f"AppController: Starting preview for {self.active_camera_config['name']}"
        )
        self.camera_service.start_camera(
            self.active_camera_config, self._internal_frame_router, record=False
        )

    def stop_preview(self) -> None:
        """Stops the active preview."""
        if self.active_camera_config:
            logger.info(
                f"AppController: Stopping preview for {self.active_camera_config['name']}"
            )
            self.camera_service.stop_camera(self.active_camera_config["id"])

    def start_recording(self) -> None:
        """Business logic for starting a recording session."""
        if self.is_recording or not self.active_camera_config:
            return

        logger.info(
            f"AppController: Starting recording session for {self.active_camera_config['name']}"
        )
        # Transition out of preview mode
        self.camera_service.stop_camera(self.active_camera_config["id"])

        self.is_recording = True
        self.camera_service.start_camera(
            self.active_camera_config, self._internal_frame_router, record=True
        )

    def stop_recording(self) -> None:
        """Business logic for stopping a recording session."""
        if not self.is_recording or not self.active_camera_config:
            return

        logger.info("AppController: Stopping recording session")
        self.is_recording = False

        recorded_path: Optional[str] = self.camera_service.stop_camera(
            self.active_camera_config["id"]
        )

        # Business Rule: Queue successful recordings to Drive
        if recorded_path and self.config_service.get("upload_enabled", True):
            self.upload_service.queue_file(recorded_path)

        # Transition back into preview mode
        self.start_preview()

    def shutdown(self) -> None:
        """Gracefully tears down all services."""
        logger.info("AppController: Shutting down services...")
        if self.is_recording:
            self.stop_recording()
        elif self.active_camera_config:
            self.camera_service.stop_camera(self.active_camera_config["id"])
        self.upload_service.stop()

    def _internal_frame_router(
        self, cam_id: str, raw_frame: bytes, width: int, height: int
    ) -> None:
        """
        Routes frames from the CameraService to the UI.

        Args:
            cam_id (str): The camera ID emitting the frame.
            raw_frame (bytes): The raw RGB24 video frame.
            width (int): The width of the frame.
            height (int): The height of the frame.
        """
        if not self.active_camera_config or cam_id != self.active_camera_config["id"]:
            return

        # Forward to UI
        if self._on_frame_callback:
            self._on_frame_callback(cam_id, raw_frame, width, height)

    def detect_cameras(self) -> List[Dict[str, str]]:
        """
        Runs platform-specific commands to detect all physical cameras.

        Returns:
            List[Dict[str, str]]: A list of dictionaries containing 'name' and 'device' for each camera.
        """
        detected: List[Dict[str, str]] = []

        # 1. Platform-specific detection
        if sys.platform == "darwin":
            # macOS: ffmpeg -f avfoundation -list_devices true -i ""
            cmd = ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""]
            try:
                result = subprocess.run(
                    cmd,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    text=True,
                    timeout=5,
                )
                output = result.stderr
            except Exception as e:
                logger.error(f"Error listing macOS devices: {e}")
                output = ""

            video_section = True
            for line in output.splitlines():
                if "AVFoundation audio devices" in line:
                    video_section = False
                if video_section and "[" in line and "]" in line:
                    match = re.search(r"\[(\d+)\]\s+(.+)", line)
                    if match:
                        idx = match.group(1)
                        name = match.group(2)
                        # Skip screen capture devices
                        if "capture screen" not in name.lower():
                            detected.append({"name": name, "device": idx})

        elif sys.platform.startswith("linux"):
            # Linux: glob sysfs video4linux
            import glob

            for path in sorted(glob.glob("/sys/class/video4linux/video*")):
                dev_name = os.path.basename(path)
                dev_path = f"/dev/{dev_name}"
                name_file = os.path.join(path, "name")
                if os.path.exists(name_file):
                    try:
                        with open(name_file, "r") as f:
                            name = f.read().strip()
                        if "metadata" not in name.lower():
                            detected.append({"name": name, "device": dev_path})
                    except Exception as e:
                        logger.error(f"Error reading sysfs for {dev_name}: {e}")
        else:
            # Windows / Fallback
            cmd = ["ffmpeg", "-f", "dshow", "-list_devices", "true", "-i", "dummy"]
            try:
                result = subprocess.run(
                    cmd,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    text=True,
                    timeout=5,
                )
                output = result.stderr
            except Exception as e:
                logger.error(f"Error listing Windows devices: {e}")
                output = ""

            for line in output.splitlines():
                if "(video)" in line:
                    match = re.search(r'"([^"]+)"', line)
                    if match:
                        name = match.group(1)
                        detected.append({"name": name, "device": f"video={name}"})

        # Remove duplicate device paths if any
        seen = set()
        unique_detected: List[Dict[str, str]] = []
        for d in detected:
            if d["device"] not in seen:
                seen.add(d["device"])
                unique_detected.append(d)

        return unique_detected
