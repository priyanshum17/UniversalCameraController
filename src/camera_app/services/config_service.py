import json
import os
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class ConfigService:
    """
    Manages loading and saving configuration from a JSON file.
    
    This service abstracts the configuration layer, allowing the backend
    to be easily swapped to Google Sheets or a database in the future.
    """
    def __init__(self, config_path: str = "src/camera_app/config.json") -> None:
        """
        Initializes the ConfigService.

        Args:
            config_path (str): The file path to the JSON configuration file.
        """
        self.config_path: str = config_path
        self._config: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """
        Loads the configuration from the JSON file into memory.

        Raises:
            FileNotFoundError: If the configuration file does not exist.
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found at {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            self._config = json.load(f)

    def save(self) -> None:
        """Saves the current in-memory configuration back to the JSON file."""
        with open(self.config_path, 'w') as f:
            json.dump(self._config, f, indent=4)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieves a value from the global configuration.

        Args:
            key (str): The configuration key to retrieve.
            default (Any, optional): The default value to return if the key is not found.

        Returns:
            Any: The value associated with the key, or the default value.
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Sets a value in the global configuration and saves it to disk.

        Args:
            key (str): The configuration key to set.
            value (Any): The value to store.
        """
        self._config[key] = value
        self.save()

    def get_cameras(self) -> List[Dict[str, Any]]:
        """
        Retrieves the list of all camera configurations.

        Returns:
            List[Dict[str, Any]]: A list of camera configuration dictionaries.
        """
        return self._config.get("cameras", [])

    def get_camera(self, cam_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the configuration for a specific camera by ID.

        Args:
            cam_id (str): The unique identifier of the camera.

        Returns:
            Optional[Dict[str, Any]]: The camera configuration, or None if not found.
        """
        for cam in self.get_cameras():
            if cam["id"] == cam_id:
                return cam
        return None

    def update_camera(self, cam_id: str, updates: Dict[str, Any]) -> bool:
        """
        Updates specific fields in a camera's configuration and saves it.

        Args:
            cam_id (str): The unique identifier of the camera.
            updates (Dict[str, Any]): A dictionary of key-value pairs to update.

        Returns:
            bool: True if the camera was found and updated, False otherwise.
        """
        cameras = self.get_cameras()
        for i, cam in enumerate(cameras):
            if cam["id"] == cam_id:
                cameras[i].update(updates)
                self.save()
                return True
        return False
