"""Select 24-class pilot candidates to promote to formal (validation-only)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from v2.select import select


def select_rml24(config_path: str | Path = "configs/rml24_base.yaml",
                 search_space_path: str | Path = "configs/search_space_rml24.yaml",
                 pilot_root: str | Path | None = None,
                 n_top: int | None = None,
                 output_path: str | Path | None = None) -> dict[str, Any]:
    """Promote the top 24-class pilot trials; writes ``selected_candidates.json``."""
    if pilot_root is None:
        base_root = "runs/rml24_base"
        pilot_root = f"{base_root}/pilot"
    return select(config_path, search_space_path, pilot_root, n_top, output_path)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/rml24_base.yaml")
    parser.add_argument("--search-space", default="configs/search_space_rml24.yaml")
    parser.add_argument("--pilot-root", required=True)
    parser.add_argument("--n-top", type=int, default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    print(select_rml24(args.config, args.search_space, args.pilot_root, args.n_top, args.output))


if __name__ == "__main__":
    main()
