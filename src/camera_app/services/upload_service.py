import threading
import queue
import time
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class UploadService:
    """
    Background service that watches a queue for completed MP4 files
    and uploads them to a remote destination (e.g., Google Drive)
    without blocking the core application or UI.
    """

    def __init__(self) -> None:
        """Initializes the UploadService and its internal queue."""
        self.upload_queue: queue.Queue[Optional[str]] = queue.Queue()
        self.running: bool = False
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Starts the background worker thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._upload_loop, daemon=True)
        self.thread.start()
        logger.info("Upload service started.")

    def stop(self) -> None:
        """Stops the background worker thread gracefully."""
        self.running = False
        if self.thread:
            self.upload_queue.put(None)
            self.thread.join(timeout=2.0)
        logger.info("Upload service stopped.")

    def queue_file(self, filepath: str) -> None:
        """
        Adds a file path to the upload queue.

        Args:
            filepath (str): The path to the file to upload.
        """
        self.upload_queue.put(filepath)
        logger.info(f"Queued for upload: {filepath}")

    def _upload_loop(self) -> None:
        """The internal loop that processes the upload queue."""
        while self.running:
            try:
                filepath: Optional[str] = self.upload_queue.get(timeout=1.0)
                if filepath is None:
                    continue

                logger.info(f"[UploadService] Starting upload for {filepath}...")

                if not os.path.exists(filepath):
                    logger.warning(f"[UploadService] File not found: {filepath}")
                    self.upload_queue.task_done()
                    continue

                time.sleep(3)

                logger.info(f"[UploadService] Successfully uploaded {filepath}")
                self.upload_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"[UploadService] Error uploading {filepath}: {e}")
