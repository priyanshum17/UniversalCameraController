#!/bin/bash
set -e

echo "Universal Camera Controller - System Setup Script"
echo "================================================="

# 1. Ensure uv is installed
if ! command -v uv &> /dev/null; then
    echo "uv package manager not found. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Source environment to make uv available in this shell
    if [ -f "$HOME/.local/bin/env" ]; then
        source "$HOME/.local/bin/env"
    fi
    # Add to path just in case
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "Syncing Python dependencies..."
uv sync

# 2. Raspberry Pi Auto-Detection
is_pi=false
if [ -f /sys/firmware/devicetree/base/model ]; then
    if grep -iq "Raspberry Pi" /sys/firmware/devicetree/base/model; then
        is_pi=true
    fi
fi

if [ "$is_pi" = true ]; then
    echo "Raspberry Pi detected!"
    echo "Installing system-level libraries for FFmpeg, SDL2, and Kivy (requires sudo)..."
    
    # Update and install system dependencies
    sudo apt-get update -y
    sudo apt-get install -y ffmpeg \
                            libsdl2-dev \
                            libsdl2-image-dev \
                            libsdl2-mixer-dev \
                            libsdl2-ttf-dev \
                            libgles2-mesa-dev \
                            libegl1-mesa-dev \
                            libgl1-mesa-dev \
                            xclip \
                            xsel \
                            mtdev-tools

    # 3. Create a shell launcher script
    echo "Generating launch script: run_app.sh..."
    cat << 'EOF' > run_app.sh
#!/bin/bash
# Auto-generated launcher for Universal Camera Controller
cd "$(dirname "$0")"

# Force Kivy to use SDL2 window provider and GLES backend on Raspberry Pi
export KIVY_GL_BACKEND=sdl2
export KIVY_WINDOW=sdl2

echo "Starting Camera Application..."
uv run main.py
EOF
    chmod +x run_app.sh
    echo "run_app.sh generated successfully."

    # 4. Create Desktop Shortcut (.desktop)
    DESKTOP_DIR="$HOME/Desktop"
    if [ -d "$DESKTOP_DIR" ]; then
        echo "Generating Desktop shortcut launcher..."
        cat << EOF > "$DESKTOP_DIR/CameraController.desktop"
[Desktop Entry]
Name=Camera Controller
Comment=Launch Universal Camera App
Exec=$(pwd)/run_app.sh
Icon=video-display
Terminal=true
Type=Application
Categories=Utility;
EOF
        chmod +x "$DESKTOP_DIR/CameraController.desktop"
        echo "Desktop shortcut created at: $DESKTOP_DIR/CameraController.desktop"
    else
        echo "Desktop directory not found. Skipping desktop shortcut generation."
    fi
else
    echo "System is not a Raspberry Pi. Only Python synchronization performed."
    echo "If you are running on macOS or Linux, ensure you have 'ffmpeg' installed on your system path."
fi

echo "================================================="
echo "Setup complete! Run the app using: make run"
