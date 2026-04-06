#!/usr/bin/env python3
import os
import shutil
from pathlib import Path

# Files and patterns to delete
TO_DELETE = [
    ".DS_Store",
    "geosupply_errors.log",
    # All backup files
    "*.bak.*",
    # Specific backup files (in case glob misses)
    ".env.example.bak.34642",
    ".gitignore.bak.34574",
    ".gitignore.bak.34642",
    "CONTRIBUTING.md.bak.34642",
    "Makefile.bak.34642",
    "requirements.txt.bak.34574",
    "requirements.txt.bak.34642",
]

def cleanup():
    root = Path(".")
    deleted = []

    for pattern in TO_DELETE:
        if "*" in pattern:
            # Handle globs
            for f in root.glob(pattern):
                if f.is_file():
                    f.unlink()
                    deleted.append(str(f))
        else:
            # Exact files
            f = root / pattern
            if f.is_file():
                f.unlink()
                deleted.append(str(f))

    print("✅ Deleted the following files:")
    for f in deleted:
        print(f"   • {f}")

    # Optional: remove empty folders if any
    print("\nRepo is now clean!")
    print("Next steps:")
    print("   1. Test your app: streamlit run geosupply_analyzer.py")
    print("   2. git add .")
    print("   3. git commit -m 'Cleanup: remove backup files, .DS_Store and log'")
    print("   4. git push")

if __name__ == "__main__":
    cleanup()