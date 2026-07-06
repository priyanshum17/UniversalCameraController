.PHONY: run setup format

run:
	uv run main.py

setup:
	uv sync

format:
	uv tool run ruff format src/ main.py
