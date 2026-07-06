import subprocess
import os
import time
import sys
import threading
import logging
from typing import Any, Callable, Dict, Optional
from kivy.clock import (
    Clock,
)  # Still needed here because we schedule the frame callback to UI thread

logger = logging.getLogger(__name__)


class CameraWorker:
    """
    Manages a single FFmpeg subprocess for a camera.

    This class wraps the FFmpeg binary, configuring it to capture from the
    specified device, encode to MP4, and simultaneously output a raw RGB24
    stream to stdout for the application to consume.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initializes the CameraWorker.

        Args:
            config (Dict[str, Any]): The camera configuration dictionary.
        """
        self.config: Dict[str, Any] = config
        self.process: Optional[subprocess.Popen] = None
        self.recording_path: Optional[str] = None
        self.width: int = int(config["resolution"].split("x")[0])
        self.height: int = int(config["resolution"].split("x")[1])

    def start(self, base_record_dir: str) -> None:
        """
        Starts the FFmpeg subprocess.

        Captures the device feed to an MP4 file and a raw video stream.

        Args:
            base_record_dir (str): The directory where recordings should be saved.
        """
        if self.process is not None:
            return

        device: str = self.config["device"]
        fps: int = self.config["fps"]

        os.makedirs(base_record_dir, exist_ok=True)
        timestamp: str = time.strftime("%Y%m%d-%H%M%S")
        self.recording_path = os.path.join(
            base_record_dir, f"{self.config['id']}_{timestamp}.mp4"
        )

        input_format: str
        if sys.platform == "darwin":
            input_format = "avfoundation"
        elif sys.platform.startswith("linux"):
            input_format = "v4l2"
        else:
            input_format = "dshow"

        cmd: list[str] = [
            "ffmpeg",
            "-y",
            "-f",
            input_format,
            "-framerate",
            str(fps),
            "-video_size",
            self.config["resolution"],
            "-i",
            device,
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-f",
            "mp4",
            self.recording_path,
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            self.config["resolution"],
            "-",
        ]

        self.process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8
        )
        logger.info(f"[{self.config['id']}] Started FFmpeg: {self.recording_path}")

    def stop(self) -> Optional[str]:
        """
        Stops the FFmpeg subprocess gracefully.

        Returns:
            Optional[str]: The path to the recorded MP4 file, or None if not started.
        """
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None
            logger.info(f"[{self.config['id']}] Stopped FFmpeg.")
            return self.recording_path
        return None


class StreamReceiver:
    """
    Reads the raw video stream from a CameraWorker in a background thread.

    Dispatches the read frames back to the main thread via Kivy's Clock.
    """

    def __init__(
        self,
        camera_worker: CameraWorker,
        on_frame_callback: Callable[[str, bytes, int, int], None],
    ) -> None:
        """
        Initializes the StreamReceiver.

        Args:
            camera_worker (CameraWorker): The worker managing the FFmpeg process.
            on_frame_callback (Callable): The function to call when a full frame is received.
        """
        self.worker: CameraWorker = camera_worker
        self.on_frame_callback: Callable[[str, bytes, int, int], None] = (
            on_frame_callback
        )
        self.running: bool = False
        self.thread: Optional[threading.Thread] = None
        self.frame_size: int = self.worker.width * self.worker.height * 3

    def start(self) -> None:
        """Starts the background thread to read from the FFmpeg stdout pipe."""
        if not self.worker.process or not self.worker.process.stdout:
            logger.error(
                f"[{self.worker.config['id']}] Cannot start receiver: process not running."
            )
            return

        self.running = True
        self.thread = threading.Thread(target=self._read_stream, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        """Stops the background reading thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)

    def _read_stream(self) -> None:
        """The internal loop that continuously reads raw frames from stdout."""
        logger.info(f"[{self.worker.config['id']}] Stream receiver thread started.")
        while (
            self.running and self.worker.process and self.worker.process.poll() is None
        ):
            raw_frame: bytes = self.worker.process.stdout.read(self.frame_size)
            if len(raw_frame) != self.frame_size:
                break
            Clock.schedule_once(
                lambda dt, frame=raw_frame: self._update_texture(frame), 0
            )

        logger.info(f"[{self.worker.config['id']}] Stream receiver thread stopped.")

    def _update_texture(self, raw_frame: bytes) -> None:
        """Forwards the frame data to the provided callback."""
        self.on_frame_callback(
            self.worker.config["id"], raw_frame, self.worker.width, self.worker.height
        )


class CameraService:
    """
    Service to orchestrate CameraWorkers and Receivers.

    Provides a high-level API to start and stop camera recordings without
    worrying about the underlying subprocesses or threads.
    """

    def __init__(self, config_service: Any) -> None:
        """
        Initializes the CameraService.

        Args:
            config_service (ConfigService): The global configuration service.
        """
        self.config_service: Any = config_service
        self.workers: Dict[str, CameraWorker] = {}
        self.receivers: Dict[str, StreamReceiver] = {}

    def start_camera(
        self, cam_id: str, on_frame_callback: Callable[[str, bytes, int, int], None]
    ) -> Optional[CameraWorker]:
        """
        Starts recording and streaming for a specific camera.

        Args:
            cam_id (str): The unique ID of the camera to start.
            on_frame_callback (Callable): Callback to receive the video frames.

        Returns:
            Optional[CameraWorker]: The started worker, or None if the config was invalid.
        """
        record_dir: str = self.config_service.get("recording_dir", "./recordings")
        cam_config: Optional[Dict[str, Any]] = self.config_service.get_camera(cam_id)
        if cam_config:
            worker = CameraWorker(cam_config)
            self.workers[cam_id] = worker
            worker.start(record_dir)

            receiver = StreamReceiver(worker, on_frame_callback)
            self.receivers[cam_id] = receiver
            receiver.start()

            return worker
        return None

    def stop_camera(self, cam_id: str) -> Optional[str]:
        """
        Stops the camera and cleans up associated threads/processes.

        Args:
            cam_id (str): The unique ID of the camera to stop.

        Returns:
            Optional[str]: The file path to the completed MP4 recording, if applicable.
        """
        receiver = self.receivers.pop(cam_id, None)
        if receiver:
            receiver.stop()

        worker = self.workers.pop(cam_id, None)
        if worker:
            return worker.stop()
        return None
