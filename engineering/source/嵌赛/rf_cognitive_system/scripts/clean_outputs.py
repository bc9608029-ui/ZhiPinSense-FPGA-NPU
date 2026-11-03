"""Delete only regenerable output artifacts while preserving .gitkeep files."""

from __future__ import annotations

from pathlib import Path
import shutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "outputs"


def main() -> None:
    removed = 0
    for folder_name in ("checkpoints", "figures", "logs", "tables"):
        folder = (OUTPUT_ROOT / folder_name).resolve()
        if OUTPUT_ROOT.resolve() not in folder.parents:
            raise RuntimeError(f"Refusing unsafe cleanup target: {folder}")
        for path in folder.iterdir():
            if path.is_file() and path.name != ".gitkeep":
                path.unlink()
                removed += 1
    cache_directories = [PROJECT_ROOT / ".pytest_cache", *PROJECT_ROOT.rglob("__pycache__")]
    removed_caches = 0
    for cache in cache_directories:
        resolved = cache.resolve()
        if PROJECT_ROOT.resolve() not in resolved.parents:
            raise RuntimeError(f"Refusing unsafe cache cleanup target: {resolved}")
        if resolved.is_dir():
            shutil.rmtree(resolved)
            removed_caches += 1
    print(f"Removed {removed} regenerable output files and {removed_caches} cache directories from {PROJECT_ROOT}")


if __name__ == "__main__":
    main()
