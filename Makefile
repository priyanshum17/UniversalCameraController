.PHONY: run run-sequence setup format

run:
	uv run main.py

run-sequence:
	uv run examples/sequence_recorder.py --cameras cam1 cam2 --durations 5 5 --loops 1 --interval 1.0

setup:
	uv sync

format:
	uv tool run ruff format src/ main.py examples/
