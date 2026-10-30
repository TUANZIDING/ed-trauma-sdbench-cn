#!/usr/bin/env python3
"""把 cases/v0.1/*.md（YAML front matter + 正文）打包为 SDBench 单文件数据集。
Build the SDBench single-file dataset (dataset.json) from the Markdown case sources.

输出 / Output:
  data/processed_case_data/ed-trauma-cn/dataset.json   （SDBench 加载器要求的固定文件名）
  data/processed_case_data/ed-trauma-cn/case-metav0.1.json （教学元数据：鉴别、关键线索、指南）

用法 / Usage:
  python scripts/build-datasetv0.1.py [--check]
"""
import argparse
import json
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASE_DIR = ROOT / "cases" / "v0.1"
OUT_DIR = ROOT / "data" / "processed_case_data" / "ed-trauma-cn"
REQUIRED = ["case_id", "case_title", "final_diagnosis", "case_summary"]
META_KEYS = ["difficulty", "topic", "key_differentials", "key_clues", "guideline_refs"]


def parse_case(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path.name}: 缺少 YAML front matter")
    _, front, body = text.split("---", 2)
    meta = yaml.safe_load(front)
    meta["full_text"] = body.strip()
    meta["source_file"] = path.name
    return meta


def validate(case: dict) -> list[str]:
    errs = []
    for k in REQUIRED + ["full_text"]:
        if not isinstance(case.get(k), str) or not case[k].strip():
            errs.append(f"{case.get('source_file')}: 字段 {k} 缺失或为空")
    # case_summary 不得泄露诊断：粗查参考诊断的中文主词是否出现在摘要中
    dx_head = case.get("final_diagnosis", "").split("（")[0][:6]
    if dx_head and dx_head in case.get("case_summary", ""):
        errs.append(f"{case['source_file']}: case_summary 可能泄露诊断（含 '{dx_head}'）")
    if not case.get("case_sets"):
        errs.append(f"{case.get('source_file')}: 缺少 case_sets")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验不写文件")
    args = ap.parse_args()

    cases = [parse_case(p) for p in sorted(CASE_DIR.glob("case*.md"))]
    errs = [e for c in cases for e in validate(c)]
    ids = [c["case_id"] for c in cases]
    if len(ids) != len(set(ids)):
        errs.append("case_id 有重复")
    if errs:
        print("\n".join(errs))
        return 1

    dataset, meta = [], {}
    for c in cases:
        item = {k: c[k] for k in REQUIRED + ["full_text", "case_sets"]}
        if "tests" in c:
            item["tests"] = c["tests"]
        if "estimated_clinician_visits" in c:
            item["estimated_clinician_visits"] = c["estimated_clinician_visits"]
        dataset.append(item)
        meta[c["case_id"]] = {k: c.get(k) for k in META_KEYS} | {
            "final_diagnosis": c["final_diagnosis"],
            "key_tests": [t["name"] for t in c.get("tests", [])],
            "source_file": c["source_file"],
        }

    print(f"校验通过：{len(dataset)} 个病例；"
          + "，".join(f"{s}={sum(s in d['case_sets'] for d in dataset)}" for s in ["dev", "test"]))
    if args.check:
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "dataset.json").write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "case-metav0.1.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {OUT_DIR.relative_to(ROOT)}/dataset.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
