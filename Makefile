.PHONY: help install clean test lint build deploy

help:
	@echo "Commands:"
	@echo "  install    : Install dependencies"
	@echo "  clean      : Clean up build artifacts"
	@echo "  test       : Run tests"
	@echo "  lint       : Run linter"
	@echo "  build      : Build SAM application"
	@echo "  deploy     : Deploy SAM application"

install:
	pip install -r requirements.txt

clean:
	rm -rf .aws-sam
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete

test:
	pytest tests/

lint:
	# TODO: Add linter command (e.g., flake8, black, ruff)
	echo "Linter not configured yet."

build:
	sam build

deploy:
	sam deploy --guided
