.PHONY: run setup format

run:
	uv run main.py

setup:
	chmod +x setup.sh
	./setup.sh

format:
	uv tool run ruff format src/ main.py
