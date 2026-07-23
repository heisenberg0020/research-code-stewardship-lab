# Coding-agent benchmark evidence

This directory records the source data and rendering method for the benchmark figure embedded in the bilingual READMEs.

## What the figure contains

The figure redraws three results reported by OpenAI for GPT-5.6 Sol on 2026-07-09:

| Benchmark | Reported score | Capability represented |
|---|---:|---|
| SWE-Bench Pro | 64.6% | Repository-level software issue resolution |
| DeepSWE v1.1 | 72.7% | Long-horizon engineering in real codebases |
| Terminal-Bench 2.1 | 88.8% | Command-line planning, iteration, and tool coordination |

Primary source: [GPT-5.6: Frontier intelligence that scales with your ambition](https://openai.com/index/gpt-5-6/).

The values are each benchmark's native score. They are **not directly interchangeable**, are not averaged, and do not mean that an agent can complete a corresponding percentage of arbitrary programming or research work.

## Why SWE-bench Verified is not used

OpenAI reported in February 2026 that SWE-bench Verified had become increasingly contaminated and contained test-quality problems, and recommended SWE-Bench Pro for evaluating frontier systems. See [Why SWE-bench Verified no longer measures frontier coding capabilities](https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/).

## Research-engineering boundary

The coding results support claims about repository work, long-horizon implementation, and terminal coordination. They do not establish paper fidelity or scientific validity. Separate research benchmarks illustrate that broader tasks are measurable and materially harder:

- [MLE-bench](https://openai.com/index/mle-bench/) covers 75 Kaggle competitions; its publication reported that the best tested system reached at least bronze-medal level in 16.9% of competitions.
- [PaperBench](https://github.com/openai/frontier-evals/tree/main/project/paperbench) evaluates end-to-end replication of 20 ICML papers; its published leaderboard reports 26.0% for the best listed full-replication system under a 36-hour limit.
- [CORE-Bench](https://github.com/siegelz/core-bench) evaluates computational reproduction of published research repositories.

Those results use different systems, dates, budgets, tasks, and metrics. They are cited as scope evidence, not plotted against GPT-5.6 Sol and not treated as a single capability curve.

## Reproduce the figure

The renderer uses only the Python standard library:

```bash
python docs/benchmark-evidence/render_chart.py
python docs/benchmark-evidence/render_chart.py --check
```

The SVG is an original visualization by this repository and is covered by the repository's documentation license. No third-party chart artwork, logos, benchmark tasks, or model artifacts are redistributed. Benchmark names and reported values remain attributed to their respective sources.
