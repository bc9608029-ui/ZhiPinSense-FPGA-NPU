"""Convert Vivado ILA tensor probes to the frozen board-capture CSV schema."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


VALUE_COLUMNS = {
    "m_iq_i_data[7:0]": "iq_i_int8",
    "m_iq_q_data[7:0]": "iq_q_int8",
    "m_power_data[7:0]": "power_int8",
    "m_lag_re_data[7:0]": "lag_re_int8",
    "m_lag_im_data[7:0]": "lag_im_int8",
}
ADDRESS_COLUMNS = {
    "m_iq_i_addr[10:0]": "iq_i_addr",
    "m_iq_q_addr[10:0]": "iq_q_addr",
    "m_power_addr[11:0]": "power_addr",
    "m_lag_re_addr[11:0]": "lag_re_addr",
    "m_lag_im_addr[11:0]": "lag_im_addr",
}
OUTPUT_COLUMNS = [
    "frame_id",
    "sample_index",
    "buffer_id",
    "iq_i_int8",
    "iq_q_int8",
    "power_int8",
    "lag_re_int8",
    "lag_im_int8",
    "iq_i_addr",
    "iq_q_addr",
    "power_addr",
    "lag_re_addr",
    "lag_im_addr",
    "frame_start",
    "frame_done",
    "frame_error",
    "irq",
]


def hex_int(text: str) -> int:
    return int(text.strip(), 16)


def signed8(text: str) -> int:
    value = hex_int(text)
    return value - 256 if value & 0x80 else value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    with args.input.open(newline="", encoding="utf-8-sig") as source:
        rows = list(csv.DictReader(source))
    if not rows or len(rows) % 1024 != 0:
        raise SystemExit(f"expected a nonzero multiple of 1024 qualified writes, found {len(rows)}")

    converted: list[dict[str, int]] = []
    for index, row in enumerate(rows):
        if hex_int(row["m_write_valid"]) != 1 or hex_int(row["m_write_ready"]) != 1:
            raise SystemExit(f"row {index} is not an accepted tensor write")
        out: dict[str, int] = {
            "frame_id": hex_int(row["m_frame_id[31:0]"]),
            "sample_index": hex_int(row["m_sample_index[9:0]"]),
            "buffer_id": hex_int(row["m_buffer_id"]),
            "frame_start": hex_int(row["m_frame_start"]),
            "frame_done": hex_int(row["m_frame_done"]),
            "frame_error": hex_int(row["m_frame_error"]),
            "irq": hex_int(row["m_irq"]),
        }
        out.update({dst: signed8(row[src]) for src, dst in VALUE_COLUMNS.items()})
        out.update({dst: hex_int(row[src]) for src, dst in ADDRESS_COLUMNS.items()})
        converted.append(out)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(converted)
    print(
        f"converted_rows={len(converted)} "
        f"frame_ids={converted[0]['frame_id']}..{converted[-1]['frame_id']}"
    )


if __name__ == "__main__":
    main()
