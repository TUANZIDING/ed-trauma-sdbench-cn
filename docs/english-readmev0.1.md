<p align="center">
  <img src="coverv0.1.svg" width="100%" alt="Concept cover: from a one-line summary, ask, test and image step by step, then reach a scored, costed diagnosis">
</p>

<h1 align="center">ED Trauma SDBench-CN</h1>

<p align="center">
  <strong>Start from one sentence, ask and order step by step, and see who gets it right at the lowest cost.</strong>
</p>

<p align="center"><a href="../README.md">简体中文</a> · English</p>

> For research and education only. Not a medical device. Microsoft has filed a US patent application (No. 19/722,651) covering the SDBench evaluation framework. This project is not affiliated with Microsoft.

## What it is

A set of 15 synthetic Chinese emergency-trauma cases (dev 9 / test 6) in [Microsoft SDBench](https://github.com/microsoft/sdbench) format (Nori et al., Science 2026;394(6822):423-428, doi:10.1126/science.aeh7930). The same cases serve two purposes:

- **A · Benchmark models** with the official SDBench harness, priced in RMB.
- **B · Train residents and students**: the learner sees only a one-line summary, asks questions and orders tests, then commits to a diagnosis and receives a feedback report.

<p align="center"><img src="flowv0.2.svg" width="100%" alt="Workflow diagram"></p>

## Contents

| Part | Path |
| --- | --- |
| Cases (Markdown + YAML front matter) | `cases/v0.1/` |
| SDBench dataset (generated) | `data/processed_case_data/ed-trauma-cn/dataset.json` |
| RMB cost sheet, 58 items with sources | `costing/cn-cost-sheetv0.1.csv`, `costing/cost-sourcesv0.1.md` |
| RMB costing and feedback-report scripts | `scripts/` |
| Teaching-mode design | `docs/teaching-mode-designv0.1.md` |
| Pilot run (unofficial) | `examples/pilot-runv0.1/` |

## Costing scope

Each round costs an ED consultation fee of CNY 25; each test is priced from public Jiangsu (Wuxi/Suzhou) government price lists. Only diagnostic service fees are counted, as in SDBench. Contrast agents, consumables, drugs, blood products, monitoring and therapeutic procedures are **not** included, so totals are far below a real resuscitation-room bill. Unverified or unmatched items are listed, never estimated.

## Pilot (unofficial)

Hark's own model ran all 15 cases through a simplified keyword gatekeeper, scored by the case author: 15/15 correct, mean score 4.87, mean CNY 700.6 per case. This is not the official harness and is not comparable with the paper. Known issue: a single "physical exam" request returns all key signs, making cases too easy.

## Quick start

See the Chinese [Quick start](../README.md#quick-start); commands are identical.

## License

MIT for original cases, docs, SVGs and scripts, retaining the Microsoft SDBench copyright notice. NEJM and MIMIC data are licensed separately and are never included.
