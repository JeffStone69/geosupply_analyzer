#!/usr/bin/env python3
"""
setup_repo.py
Expert Python DevOps setup for GeoSupply Analyzer
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# ANSI colors
COLORS = {
    "success": "\033[92m",
    "info": "\033[94m",
    "warning": "\033[93m",
    "error": "\033[91m",
    "bold": "\033[1m",
    "end": "\033[0m",
}

def cprint(color: str, message: str) -> None:
    print(f"{COLORS.get(color, '')}{message}{COLORS['end']}")

def confirm(prompt: str) -> bool:
    while True:
        answer = input(f"{prompt} [y/N]: ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no", ""):
            return False
        cprint("warning", "Please answer y or n.")

def run_git_command(cmd: List[str], cwd: Optional[Path] = None) -> None:
    subprocess.check_call(cmd, cwd=cwd)

def backup_file(path: Path) -> None:
    if path.exists():
        backup = path.with_suffix(f"{path.suffix}.bak")
        if backup.exists():
            backup = path.with_suffix(f"{path.suffix}.bak.{os.getpid()}")
        path.rename(backup)
        cprint("warning", f"→ Backed up existing {path} to {backup}")

def write_file(path: Path, content: str, description: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    if existed:
        cprint("warning", f"→ {description} already exists → updating safely")
        backup_file(path)
    else:
        cprint("info", f"→ Creating {description}...")
    try:
        path.write_text(content.strip() + "\n", encoding="utf-8")
        cprint("success", f"✅ {'Updated' if existed else 'Created'} {path.name}")
        return True
    except Exception as e:
        cprint("error", f"❌ Failed to write {path}: {e}")
        return False

def main() -> None:
    parser = argparse.ArgumentParser(description="Setup best-practice files for GeoSupply Analyzer.")
    parser.add_argument("--auto-commit", action="store_true", help="Automatically commit and push")
    args = parser.parse_args()

    root = Path.cwd().resolve()
    main_app = root / "geosupply_analyzer.py"
    if not main_app.is_file():
        cprint("error", "❌ geosupply_analyzer.py not found!\nRun this script from the project root.")
        sys.exit(1)

    cprint("bold", "\n🚀 GeoSupply Analyzer Best-Practice Setup")
    cprint("info", "=" * 70)

    files_created_or_updated: List[Path] = []

    # requirements.txt
    requirements_content = """streamlit>=1.42.0
pandas>=2.2.3
plotly>=5.24.1
yfinance>=0.2.52
requests>=2.32.3
numpy>=2.1.3
"""
    if write_file(root / "requirements.txt", requirements_content, "requirements.txt"):
        files_created_or_updated.append(root / "requirements.txt")

    # .gitignore
    gitignore_content = """__pycache__/
*.py[cod]
*.so
.Python
build/
dist/
*.egg-info/
.env
.venv
venv/
.streamlit/cache/
*.log
*.tmp
*.bak
.DS_Store
.vscode/
.idea/
data/
cache/
"""
    if write_file(root / ".gitignore", gitignore_content, ".gitignore"):
        files_created_or_updated.append(root / ".gitignore")

    # .env.example
    env_example_content = """GROK_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# Optional
TAILSCALE_AUTH_KEY=
DATA_DIR=./data
"""
    if write_file(root / ".env.example", env_example_content, ".env.example"):
        files_created_or_updated.append(root / ".env.example")

    # .streamlit/config.toml
    config_toml_content = """[server]
headless = false
port = 8501
enableCORS = false
enableXsrfProtection = false
maxUploadSize = 200

[theme]
primaryColor = "#00b4d8"
backgroundColor = "#0e1117"
secondaryBackgroundColor = "#262730"
textColor = "#fafafa"
"""
    (root / ".streamlit").mkdir(exist_ok=True)
    if write_file(root / ".streamlit" / "config.toml", config_toml_content, ".streamlit/config.toml"):
        files_created_or_updated.append(root / ".streamlit" / "config.toml")

    # CONTRIBUTING.md
    contributing_content = """# Contributing to GeoSupply Analyzer

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with `streamlit run geosupply_analyzer.py`
5. Open a Pull Request
"""
    if write_file(root / "CONTRIBUTING.md", contributing_content, "CONTRIBUTING.md"):
        files_created_or_updated.append(root / "CONTRIBUTING.md")

    # Makefile
    makefile_content = """# GeoSupply Analyzer Makefile
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
"""
    if write_file(root / "Makefile", makefile_content, "Makefile"):
        files_created_or_updated.append(root / "Makefile")

    if not files_created_or_updated:
        cprint("success", "\n🎉 Everything was already up-to-date!")
        sys.exit(0)

    cprint("bold", f"\n📦 {len(files_created_or_updated)} file(s) created/updated.")

    should_commit = args.auto_commit or confirm("\nCommit these changes and push to GitHub?")
    if should_commit:
        try:
            cprint("info", "🔄 Staging files...")
            run_git_command(["git", "add"] + [str(p) for p in files_created_or_updated])
            run_git_command(["git", "commit", "-m", "chore(setup): add/update best-practice files via setup_repo.py"])
            run_git_command(["git", "push"])
            cprint("success", "\n✅ Repository is now production-ready!")
        except Exception as e:
            cprint("error", f"⚠️ Git step failed: {e}")
    else:
        cprint("info", "\n✅ Files ready locally.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        cprint("warning", "\n⏹️ Setup interrupted.")
        sys.exit(1)
    except Exception as e:
        cprint("error", f"\n💥 Unexpected error: {e}")
        sys.exit(1)