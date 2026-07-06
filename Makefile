.PHONY: run setup format

run:
	uv run src/camera_app/main.py

setup:
	uv sync

format:
	uv tool run ruff format src/
