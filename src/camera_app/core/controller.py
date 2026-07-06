import logging
from typing import Callable, Optional
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
        self.upload_service: UploadService = UploadService()
        self.camera_service: CameraService = CameraService(self.config_service)

        # State
        self.selected_cam_id: str = self.config_service.get("selected_camera", "cam1")
        self.is_recording: bool = False
        self._on_frame_callback: Optional[Callable[[str, bytes, int, int], None]] = None

        self.upload_service.start()

    def set_frame_callback(
        self, callback: Callable[[str, bytes, int, int], None]
    ) -> None:
        """
        Registers a callback to receive video frames.

        Args:
            callback (Callable): The function to call when a frame is ready.
        """
        self._on_frame_callback = callback

    def select_camera(self, cam_id: str) -> None:
        """
        Business logic for changing the active camera.

        Args:
            cam_id (str): The unique identifier of the camera to switch to.
        """
        if cam_id == self.selected_cam_id:
            return

        logger.info(f"AppController: Switching selected camera to {cam_id}")
        self.selected_cam_id = cam_id
        self.config_service.set("selected_camera", cam_id)

        # Business Rule: If we are recording and switch feeds,
        # seamlessly stop the old and start the new.
        if self.is_recording:
            self.stop_recording()
            self.start_recording()

    def start_recording(self) -> None:
        """Business logic for starting a recording session."""
        if self.is_recording:
            return

        logger.info(
            f"AppController: Starting recording session for {self.selected_cam_id}"
        )
        self.is_recording = True

        self.camera_service.start_camera(
            self.selected_cam_id, self._internal_frame_router
        )

    def stop_recording(self) -> None:
        """Business logic for stopping a recording session."""
        if not self.is_recording:
            return

        logger.info("AppController: Stopping recording session")
        self.is_recording = False

        recorded_path: Optional[str] = self.camera_service.stop_camera(
            self.selected_cam_id
        )

        # Business Rule: Queue successful recordings to Drive
        if recorded_path and self.config_service.get("upload_enabled", True):
            self.upload_service.queue_file(recorded_path)

    def shutdown(self) -> None:
        """Gracefully tears down all services."""
        logger.info("AppController: Shutting down services...")
        self.stop_recording()
        self.upload_service.stop()

    def _internal_frame_router(
        self, cam_id: str, raw_frame: bytes, width: int, height: int
    ) -> None:
        """
        Routes frames from the CameraService to the UI.

        This is where AI inference or OpenCV processing could easily be injected
        before handing the frame to the UI.

        Args:
            cam_id (str): The camera ID emitting the frame.
            raw_frame (bytes): The raw RGB24 video frame.
            width (int): The width of the frame.
            height (int): The height of the frame.
        """
        if cam_id != self.selected_cam_id:
            return

        # Forward to UI
        if self._on_frame_callback:
            self._on_frame_callback(cam_id, raw_frame, width, height)
