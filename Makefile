# GeoSupply Analyzer Makefile
.PHONY: help install run clean setup
help:
	@echo "Available targets:"
	@echo "  install   - Install dependencies"
	@echo "  run       - Launch the Streamlit app"
	@echo "  clean     - Clean caches"
	@echo "  setup     - Run setup script"
install:
	pip install -r requirements.txt --upgrade
run:
	streamlit run geosupply_analyzer.py
clean:
	rm -rf __pycache__ .streamlit/cache/ *.log data/
setup:
	python setup_repo.py --auto-commit
