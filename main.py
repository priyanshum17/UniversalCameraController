import logging
from src.camera_app.core.controller import AppController
from src.camera_app.view.app import CameraApp

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main() -> None:
    """
    Entry point for the Universal Camera Controller application.

    Initializes the core controller (the brain) and injects it into the
    Kivy application (the view).
    """
    logger.info("Initializing Service-Oriented Camera Application...")

    # Initialize the core brain of the application
    controller = AppController()

    # Initialize the UI and inject the controller
    app = CameraApp(controller)

    # Run the application
    app.run()


if __name__ == "__main__":
    main()
