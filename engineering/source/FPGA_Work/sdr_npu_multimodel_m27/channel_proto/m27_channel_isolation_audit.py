"""M27 channel prototype 3-way isolation audit (spec §十一): train / validation /
final-test are generated from disjoint seed streams and must have zero content overlap
(distinct SHA256) and identical per-label counts (balanced).  Exits non-zero on any
violation.
"""

from __future__ import annotations

import sys

from m27_channel_contract import CHANNEL_LABELS
from m27_channel_generator import generate_all
from m27_channel_manifest import build_manifest, verify_zero_overlap


def main():
    seed = 2026
    splits = generate_all(seed=seed, samples_per_label=32)
    manifest = build_manifest(splits, seed)

    problems = []
    if not verify_zero_overlap(manifest):
        problems.append("splits overlap (duplicate content SHA)")

    # balanced per-label counts, identical across splits
    base_counts = manifest["splits"]["train"]["per_label"]
    for name in ("train", "validation", "final_test"):
        per = manifest["splits"][name]["per_label"]
        if per != base_counts:
            problems.append(f"{name} per-label counts differ from train")
        if any(c == 0 for c in per):
            problems.append(f"{name} has an empty label")
        if name == "train" and any(c != per[0] for c in per):
            problems.append("train labels not balanced")

    if problems:
        print("CHANNEL_IMPAIRMENT_ISOLATION_INVALID")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)

    print("CHANNEL_IMPAIRMENT_ISOLATION_OK (3-way disjoint, balanced)")
    print("labels:", CHANNEL_LABELS)
    print("per_label:", manifest["splits"]["train"]["per_label"])
    sys.exit(0)


if __name__ == "__main__":
    main()
