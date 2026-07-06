import os
from typing import Any, Dict, Optional
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.lang import Builder
from kivy.graphics.texture import Texture
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.clock import Clock
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
        self._selection_popup: Optional[Popup] = None

        # Register the callback so the controller knows where to send frames
        self.controller.set_frame_callback(self.on_frame_received)

        # Sync the active camera label to show the default selection
        self.update_active_camera_label()
        self.update_info_label()

        # Schedule the camera detection popup to show on startup
        Clock.schedule_once(lambda dt: self.show_detected_cameras(), 0.5)

    def update_active_camera_label(self) -> None:
        """Updates the text of the Select Camera button with the active camera name."""
        active = self.controller.active_camera_config
        btn = self.ids.camera_select_btn
        if active:
            btn.text = f"{active['name']}"
        else:
            btn.text = "Select Camera"

    def update_info_label(self) -> None:
        """Updates the info label with current FPS and Resolution."""
        active = self.controller.active_camera_config
        lbl = self.ids.info_label
        if active:
            lbl.text = f"Current Settings: {active.get('fps', '--')} FPS | {active.get('resolution', '--')}"
        else:
            lbl.text = "Current Settings: -- FPS | -- Resolution"

    def open_camera_selection_popup(self) -> None:
        """Opens a popup listing all detected physical cameras for selection."""
        detected = self.controller.detected_cameras

        content = GridLayout(cols=1, spacing=10, size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        if not detected:
            lbl = Label(
                text="No cameras detected. Close this popup and click 'Detect' to rescan.",
                size_hint_y=None,
                height=50,
            )
            content.add_widget(lbl)
        else:
            for cam in detected:
                btn = Button(
                    text=f"{cam['name']} (Device: {cam['device']})",
                    size_hint_y=None,
                    height=50,
                    background_color=(0.2, 0.5, 0.8, 1),
                )
                # Bind the click handler to select the camera and close the popup
                btn.bind(on_release=lambda instance, c=cam: self._on_camera_chosen(c))
                content.add_widget(btn)

        scroll = ScrollView(size_hint=(1, 0.8))
        scroll.add_widget(content)

        layout = BoxLayout(orientation="vertical", padding=10, spacing=10)
        layout.add_widget(scroll)

        close_btn = Button(text="Close", size_hint_y=0.2)
        layout.add_widget(close_btn)

        self._selection_popup = Popup(
            title="Choose Input Camera",
            content=layout,
            size_hint=(0.8, 0.8),
        )
        close_btn.bind(on_release=self._selection_popup.dismiss)
        self._selection_popup.open()

    def _on_camera_chosen(self, cam: Dict[str, str]) -> None:
        """Callback invoked when a camera is chosen from the selection popup."""
        if self._selection_popup:
            self._selection_popup.dismiss()
        self.controller.select_camera(cam["name"], cam["device"])
        self.update_active_camera_label()
        self.update_info_label()

    def show_detected_cameras(self) -> None:
        """Displays a popup showing the physical cameras detected on the host system."""
        detected = self.controller.detected_cameras

        content = GridLayout(cols=1, spacing=10, size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        if not detected:
            lbl = Label(
                text="No cameras detected on the system.",
                size_hint_y=None,
                height=40,
            )
            content.add_widget(lbl)
        else:
            for cam in detected:
                text = f"{cam['name']} (Port: {cam['device']})"
                lbl = Label(text=text, size_hint_y=None, height=40)
                content.add_widget(lbl)

        scroll = ScrollView(size_hint=(1, 0.8))
        scroll.add_widget(content)

        layout = BoxLayout(orientation="vertical", padding=10, spacing=10)
        layout.add_widget(scroll)

        close_btn = Button(text="Close", size_hint_y=0.2)
        layout.add_widget(close_btn)

        popup = Popup(
            title="Hardware Auto-Detection Results",
            content=layout,
            size_hint=(0.8, 0.6),
        )
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

    def open_settings_popup(self) -> None:
        """Opens a popup to change FPS and Resolution."""
        active = self.controller.active_camera_config
        if not active:
            return

        current_fps = str(active.get("fps", 30))
        current_res = active.get("resolution", "640x480")

        layout = BoxLayout(orientation="vertical", padding=10, spacing=10)

        # FPS Input
        fps_layout = BoxLayout(
            orientation="horizontal", spacing=10, size_hint_y=None, height=40
        )
        fps_layout.add_widget(Label(text="FPS:", size_hint_x=0.3))
        fps_input = TextInput(
            text=current_fps, multiline=False, input_filter="int", size_hint_x=0.7
        )
        fps_layout.add_widget(fps_input)
        layout.add_widget(fps_layout)

        # Resolution Input
        res_layout = BoxLayout(
            orientation="horizontal", spacing=10, size_hint_y=None, height=40
        )
        res_layout.add_widget(Label(text="Resolution:", size_hint_x=0.3))
        res_input = TextInput(text=current_res, multiline=False, size_hint_x=0.7)
        res_layout.add_widget(res_input)
        layout.add_widget(res_layout)

        # Apply & Close Buttons
        btn_layout = BoxLayout(
            orientation="horizontal", spacing=10, size_hint_y=None, height=50
        )
        apply_btn = Button(text="Apply", background_color=(0, 0.8, 0, 1))
        close_btn = Button(text="Cancel", background_color=(0.8, 0, 0, 1))
        btn_layout.add_widget(apply_btn)
        btn_layout.add_widget(close_btn)
        layout.add_widget(btn_layout)

        popup = Popup(title="Camera Settings", content=layout, size_hint=(0.6, 0.4))

        def on_apply(instance: Any) -> None:
            fps_val = int(fps_input.text) if fps_input.text.isdigit() else 30
            res_val = res_input.text.strip()
            if not res_val:
                res_val = "640x480"
            self.controller.update_camera_settings(fps_val, res_val)
            self.update_info_label()
            popup.dismiss()

        apply_btn.bind(on_release=on_apply)
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

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
        main_feed.canvas.ask_update()


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
