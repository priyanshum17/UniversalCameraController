import os
import sys
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from src.camera_app.core.controller import AppController
from src.camera_app.view.app import CameraApp

def main() -> None:
    """
    Entry point for the Universal Camera Controller application.
    
    Initializes the core controller (the brain) and injects it into the
    Kivy application (the view) to strictly separate concerns.
    """
    logger.info("Initializing Service-Oriented Camera Application...")
    
    # Initialize the core brain of the application
    controller: AppController = AppController()
    
    # Initialize the UI and inject the controller
    app: CameraApp = CameraApp(controller)
    
    # Run the application
    app.run()

if __name__ == '__main__':
    main()
