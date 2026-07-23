#!/usr/bin/env python3
"""Render the attributed coding-agent benchmark snapshot as a standalone SVG."""

from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path


HERE = Path(__file__).resolve().parent
DATA = HERE / "coding_agent_benchmark_snapshot.csv"
OUTPUT = HERE.parent / "figures" / "coding-agent-benchmark-profile.svg"


def load_rows() -> list[dict[str, str]]:
    with DATA.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("benchmark snapshot is empty")
    for row in rows:
        score = float(row["score"])
        if row["unit"] != "percent" or not 0 <= score <= 100:
            raise ValueError(f"unsupported score in {row['benchmark']!r}")
    return rows


def render(rows: list[dict[str, str]]) -> str:
    width, height = 1200, 650
    bar_x, bar_width = 340, 700
    colors = ("#38bdf8", "#818cf8", "#34d399")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
            'aria-labelledby="title desc">'
        ),
        '<title id="title">Published coding benchmark profile for GPT-5.6 Sol</title>',
        (
            '<desc id="desc">OpenAI-reported native scores: SWE-Bench Pro 64.6 percent, '
            "DeepSWE version 1.1 72.7 percent, and Terminal-Bench 2.1 88.8 percent. "
            "The benchmarks measure different tasks and the values should not be averaged.</desc>"
        ),
        '<rect width="1200" height="650" rx="28" fill="#0b1220"/>',
        (
            '<text x="70" y="78" fill="#f8fafc" font-family="Arial, Helvetica, sans-serif" '
            'font-size="34" font-weight="700">Published coding-agent benchmark profile</text>'
        ),
        (
            '<text x="70" y="116" fill="#94a3b8" font-family="Arial, Helvetica, sans-serif" '
            'font-size="20">GPT-5.6 Sol · OpenAI release snapshot · 2026-07-09</text>'
        ),
    ]

    for tick in range(0, 101, 20):
        x = bar_x + bar_width * tick / 100
        lines.append(
            f'<line x1="{x:.1f}" y1="160" x2="{x:.1f}" y2="500" '
            'stroke="#334155" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{x:.1f}" y="530" text-anchor="middle" fill="#94a3b8" '
            'font-family="Arial, Helvetica, sans-serif" font-size="16">'
            f"{tick}%</text>"
        )

    for index, row in enumerate(rows):
        y = 198 + index * 112
        score = float(row["score"])
        score_width = bar_width * score / 100
        name = html.escape(row["benchmark"])
        capability = html.escape(row["capability"])
        color = colors[index % len(colors)]
        lines.extend(
            [
                (
                    f'<text x="70" y="{y + 29}" fill="#f8fafc" '
                    'font-family="Arial, Helvetica, sans-serif" font-size="22" '
                    f'font-weight="700">{name}</text>'
                ),
                (
                    f'<text x="70" y="{y + 56}" fill="#94a3b8" '
                    'font-family="Arial, Helvetica, sans-serif" font-size="14">'
                    f"{capability}</text>"
                ),
                (
                    f'<rect x="{bar_x}" y="{y}" width="{bar_width}" height="48" '
                    'rx="12" fill="#1e293b"/>'
                ),
                (
                    f'<rect x="{bar_x}" y="{y}" width="{score_width:.1f}" height="48" '
                    f'rx="12" fill="{color}"/>'
                ),
                (
                    f'<text x="{bar_x + score_width - 12:.1f}" y="{y + 32}" '
                    'text-anchor="end" fill="#07111f" '
                    'font-family="Arial, Helvetica, sans-serif" font-size="20" '
                    f'font-weight="700">{score:.1f}%</text>'
                ),
            ]
        )

    lines.extend(
        [
            (
                '<text x="70" y="578" fill="#cbd5e1" '
                'font-family="Arial, Helvetica, sans-serif" font-size="17">'
                "Independent native benchmark scores — not a composite score or a capability percentage."
                "</text>"
            ),
            (
                '<text x="70" y="610" fill="#64748b" '
                'font-family="Arial, Helvetica, sans-serif" font-size="15">'
                "Source: OpenAI, “GPT-5.6: Frontier intelligence that scales with your ambition.” "
                "Chart redrawn by this repository.</text>"
            ),
            "</svg>",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed SVG does not match the source snapshot",
    )
    args = parser.parse_args()
    expected = render(load_rows())
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != expected:
            raise SystemExit(
                "benchmark figure is stale; run "
                "python docs/benchmark-evidence/render_chart.py"
            )
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
