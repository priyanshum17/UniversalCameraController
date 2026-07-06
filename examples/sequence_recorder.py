import time
import logging
import os
import sys
import argparse
from typing import List

# Ensure project root is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.camera_app.core.controller import AppController

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CameraScript")

def dummy_frame_callback(cam_id: str, raw_frame: bytes, width: int, height: int) -> None:
    """Headless frame sink."""
    pass

def run_scripted_recording(cameras: List[str], durations: List[float], loops: int, interval: float) -> None:
    """
    Executes a scripted sequence of camera recordings based on CLI parameters.
    """
    logger.info("Initializing AppController in headless scripting mode...")
    controller = AppController()
    controller.set_frame_callback(dummy_frame_callback)

    # Normalize durations array to match cameras length
    if len(durations) < len(cameras):
        # Repeat the last duration if we don't have enough
        last_dur = durations[-1] if durations else 5.0
        durations = durations + [last_dur] * (len(cameras) - len(durations))
    
    try:
        for loop_idx in range(loops):
            logger.info(f"--- Starting loop {loop_idx + 1}/{loops} ---")
            for i, cam_id in enumerate(cameras):
                duration = durations[i]
                cam_config = controller.config_service.get_camera(cam_id)
                
                if not cam_config:
                    logger.warning(f"Camera '{cam_id}' not found in config.json. Skipping.")
                    continue

                logger.info(f"Switching to camera: {cam_id} ({cam_config.get('name')})")
                controller.select_camera(cam_id)

                logger.info(f"Recording {cam_id} for {duration} seconds...")
                controller.start_recording()
                
                time.sleep(duration)

                logger.info(f"Stopping recording on {cam_id}...")
                controller.stop_recording()

                if interval > 0 and (i < len(cameras) - 1 or loop_idx < loops - 1):
                    logger.info(f"Waiting for {interval}s interval...")
                    time.sleep(interval)

    except KeyboardInterrupt:
        logger.warning("Scripted recording interrupted by user.")
    finally:
        logger.info("Releasing controller services...")
        controller.shutdown()
        logger.info("Scripted recording process terminated.")

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Headless Command Line Utility to script custom camera recording sequences."
    )
    parser.add_argument(
        "--cameras",
        nargs="+",
        default=["cam1", "cam2", "cam3"],
        help="List of camera IDs to record sequentially. Example: --cameras cam1 cam2"
    )
    parser.add_argument(
        "--durations",
        nargs="+",
        type=float,
        default=[5.0],
        help="Recording durations in seconds corresponding to each camera. Example: --durations 5 10 5"
    )
    parser.add_argument(
        "--loops",
        type=int,
        default=1,
        help="Number of times to repeat the entire recording sequence."
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Wait time (seconds) between camera switches."
    )

    args = parser.parse_args()
    run_scripted_recording(args.cameras, args.durations, args.loops, args.interval)

if __name__ == "__main__":
    main()
