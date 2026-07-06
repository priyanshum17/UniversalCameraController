import os
from typing import Any
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.lang import Builder
from kivy.graphics.texture import Texture
from src.camera_app.core.controller import AppController


class CameraAppRoot(BoxLayout):  # type: ignore
    """
    The main UI Component.

    It is entirely "dumb". It delegates all actions to the injected AppController,
    enforcing a strict MVC boundary.
    """

    def __init__(self, controller: AppController, **kwargs: Any) -> None:
        """
        Initializes the root layout and binds the controller.

        Args:
            controller (AppController): The brain of the application.
            **kwargs: Kivy layout kwargs.
        """
        super().__init__(**kwargs)
        self.controller: AppController = controller

        # Register the callback so the controller knows where to send frames
        self.controller.set_frame_callback(self.on_frame_received)

    def select_camera(self, cam_id: str) -> None:
        """Forwards camera selection events from the UI to the controller."""
        self.controller.select_camera(cam_id)

    def start_recording(self) -> None:
        """Forwards recording start events from the UI to the controller."""
        self.controller.start_recording()

    def stop_recording(self) -> None:
        """Forwards recording stop events from the UI to the controller."""
        self.controller.stop_recording()

    def on_frame_received(
        self, cam_id: str, raw_frame: bytes, width: int, height: int
    ) -> None:
        """
        Callback invoked by the AppController when a new video frame is ready.

        Updates the Kivy texture with the new raw RGB data.

        Args:
            cam_id (str): The ID of the camera providing the frame.
            raw_frame (bytes): Raw RGB24 bytes.
            width (int): Frame width.
            height (int): Frame height.
        """
        main_feed = self.ids.main_feed

        if not main_feed.texture or main_feed.texture.size != (width, height):
            main_feed.texture = Texture.create(size=(width, height), colorfmt="rgb")
            main_feed.texture.flip_vertical()

        main_feed.texture.blit_buffer(raw_frame, colorfmt="rgb", bufferfmt="ubyte")


class CameraApp(App):  # type: ignore
    """
    The Kivy application object.

    Responsible for building the initial UI tree from the .kv file
    and passing the controller into the root widget.
    """

    def __init__(self, controller: AppController, **kwargs: Any) -> None:
        """
        Initializes the application.

        Args:
            controller (AppController): The brain of the application.
            **kwargs: Kivy app kwargs.
        """
        super().__init__(**kwargs)
        self.controller: AppController = controller

    def build(self) -> CameraAppRoot:
        """
        Builds the UI tree.

        Returns:
            CameraAppRoot: The root widget of the application.
        """
        Builder.load_file(os.path.join(os.path.dirname(__file__), "main.kv"))
        return CameraAppRoot(self.controller)

    def on_stop(self) -> None:
        """Called automatically when the application window is closed."""
        self.controller.shutdown()
