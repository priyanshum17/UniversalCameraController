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

    def start(self, base_record_dir: Optional[str] = None) -> None:
        """
        Starts the FFmpeg subprocess.

        Captures the device feed. If base_record_dir is provided, encodes to MP4.
        Pipes raw RGB video at 10fps to stdout for UI rendering.

        Args:
            base_record_dir (str, optional): The directory where recordings should be saved.
                                             If None, starts in preview mode.
        """
        if self.process is not None:
            return

        device: str = self.config["device"]
        fps: int = self.config["fps"]

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
        ]

        # On Linux/v4l2, strict input video size or framerate configurations can cause
        # driver handshaking failures on custom sensors (like Arducam or FLIR). We let
        # FFmpeg auto-negotiate the input, and downsample/scale on output instead.
        if sys.platform != "linux":
            cmd += [
                "-framerate",
                str(fps),
                "-video_size",
                self.config["resolution"],
            ]

        cmd += [
            "-i",
            device,
        ]

        if base_record_dir is not None:
            # Record mode: output to file AND pipe rawvideo at 10fps
            os.makedirs(base_record_dir, exist_ok=True)
            timestamp: str = time.strftime("%Y%m%d-%H%M%S")
            self.recording_path = os.path.join(
                base_record_dir, f"{self.config['id']}_{timestamp}.mp4"
            )
            cmd += [
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-f",
                "mp4",
                self.recording_path,
            ]
        else:
            self.recording_path = None

        # Output rawvideo to stdout at 10fps
        cmd += [
            "-r",
            "10",
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
        logger.info(
            f"[{self.config['id']}] Started FFmpeg (Recording: {base_record_dir is not None}): {self.recording_path}"
        )

    def stop(self) -> Optional[str]:
        """
        Stops the FFmpeg subprocess gracefully.

        Returns:
            Optional[str]: The path to the recorded MP4 file, or None if not started.
        """
        if self.process:
            logger.info(f"[{self.config['id']}] Stopping FFmpeg process...")
            # Close stdout to break any blocking reads/writes
            if self.process.stdout:
                try:
                    self.process.stdout.close()
                except Exception as e:
                    logger.debug(f"Error closing stdout: {e}")

            self.process.terminate()
            try:
                self.process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                logger.warning(
                    f"[{self.config['id']}] FFmpeg did not stop in time. Killing..."
                )
                self.process.kill()
                self.process.wait()

            self.process = None
            logger.info(
                f"[{self.config['id']}] Stopped FFmpeg (Recording: {self.recording_path is not None}): {self.recording_path}"
            )
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
        # Flag to prevent UI event loop starvation
        self.ui_update_pending: bool = False

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
        try:
            while (
                self.running
                and self.worker.process
                and self.worker.process.poll() is None
            ):
                raw_frame: bytes = self.worker.process.stdout.read(self.frame_size)
                if len(raw_frame) != self.frame_size:
                    break

                # Only schedule the frame update if Kivy has processed the last one
                if not self.ui_update_pending:
                    self.ui_update_pending = True
                    Clock.schedule_once(
                        lambda dt, frame=raw_frame: self._update_texture(frame), 0
                    )
        except (ValueError, OSError) as e:
            logger.debug(
                f"[{self.worker.config['id']}] Stream receiver read interrupted: {e}"
            )
        finally:
            logger.info(f"[{self.worker.config['id']}] Stream receiver thread stopped.")

    def _update_texture(self, raw_frame: bytes) -> None:
        """Forwards the frame data to the provided callback."""
        try:
            self.on_frame_callback(
                self.worker.config["id"],
                raw_frame,
                self.worker.width,
                self.worker.height,
            )
        finally:
            # Done rendering; allow the next frame to be scheduled
            self.ui_update_pending = False


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
        self,
        cam_config: Dict[str, Any],
        on_frame_callback: Callable[[str, bytes, int, int], None],
        record: bool = True,
    ) -> Optional[CameraWorker]:
        """
        Starts recording and streaming for a specific camera.

        Args:
            cam_config (Dict[str, Any]): The camera configuration.
            on_frame_callback (Callable): Callback to receive the video frames.
            record (bool): If True, starts in recording mode (saves to disk).
                           If False, starts in preview mode.

        Returns:
            Optional[CameraWorker]: The started worker, or None if the config was invalid.
        """
        cam_id = cam_config.get("id", "active_cam")
        if cam_config and cam_config.get("enabled", True):
            worker = CameraWorker(cam_config)
            self.workers[cam_id] = worker

            if record:
                record_dir: str = self.config_service.get(
                    "recording_dir", "./recordings"
                )
                worker.start(record_dir)
            else:
                worker.start(None)

            receiver = StreamReceiver(worker, on_frame_callback)
            self.receivers[cam_id] = receiver
            receiver.start()

            return worker
        else:
            logger.warning(
                "CameraService: Camera configuration is invalid or disabled. Cannot start."
            )
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
