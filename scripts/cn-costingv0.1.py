#!/usr/bin/env python3
"""中文成本表计价：对 SDBench 结果 JSON 按 costing/cn-cost-sheetv0.1.csv 重新计价（人民币）。
Price SDBench result files against a replaceable Chinese cost sheet (CNY).

设计 / Design
- 不修改上游 SDBench：评测时用 `--no-compute-costs` 关闭美元计价，评测后用本脚本离线计价。
- 计价规则：每个已执行（未被 gatekeeper 拒绝）的检查按别名匹配成本表，取最长匹配别名；
  CT/MRI 按名称中出现的部位数计价（头、颈、胸、上腹、下腹、盆；"腹"未细分时算上腹+下腹）；
  问诊/查体计 0；每一轮（检查轮数 + 1）计一次急诊诊查费（对应 SDBench 每轮 clinician cost）。
- CTA 按血管计价，粗略按名称中头/颈/胸/腹出现数计根数（胸腹主动脉=2 根，与无锡文件一致）。
- 价格为空（待核实）或无法匹配的检查单独列出，不估价、不编造。
- 换成本表：用同列名的 CSV 通过 --sheet 指定即可（例如其他省份价格）。

用法 / Usage
  python scripts/cn-costingv0.1.py results/<run>/json [--sheet costing/cn-cost-sheetv0.1.csv] [--out cn-costv0.1.json]
  python scripts/cn-costingv0.1.py --price "胸腹盆增强CT"      # 调试单个检查名
"""
import argparse
import csv
import glob
import json
import os
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_SHEET = ROOT / "costing" / "cn-cost-sheetv0.1.csv"
QUESTION_PREFIX = "question for the patient:"
REJECTION_PHRASES = [
    "i can only provide specific test results or answer specific patient questions",
    "not available",
    "please request a specific diagnostic test",
]
REGION_WORDS = {"头": ["头", "颅", "head", "brain"], "颈": ["颈", "neck", "cervical"],
                "胸": ["胸", "chest", "thorax", "thoracic"], "上腹": ["上腹"], "下腹": ["下腹"],
                "盆": ["盆", "pelvis", "pelvic"]}
PER_REGION_ITEMS = {"I003", "I004", "I006", "I007"}


def load_sheet(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    index = []
    for r in rows:
        for a in filter(None, (x.strip() for x in r["aliases"].split(";"))):
            index.append((a.lower(), r))
    index.sort(key=lambda t: -len(t[0]))
    return rows, index


def count_regions(name):
    n = name.lower()
    if "全身" in n or "whole body" in n or "pan-scan" in n:
        return 6
    found = {k for k, ws in REGION_WORDS.items() if any(w in n for w in ws)}
    if ("腹" in n or "abdom" in n) and not ({"上腹", "下腹"} & found):
        found |= {"上腹", "下腹"}
    return max(1, len(found))


def price_test(name, index):
    n = name.lower()
    if n.startswith(QUESTION_PREFIX):
        return {"test": name, "item_id": "B000", "price": 0.0, "status": "问诊"}
    for alias, row in index:
        if alias in n:
            if row["price_cny"] in ("", None):
                return {"test": name, "item_id": row["item_id"], "item": row["item_cn"], "price": None, "status": "待核实"}
            if row["item_id"] in PER_REGION_ITEMS:
                qty = count_regions(name)
            elif row["item_id"] == "I005":  # CTA 按血管计：头、颈、胸、腹各按 1 根（粗略，见 README）
                qty = max(1, sum(any(w in n for w in ws) for ws in (["头", "颅"], ["颈"], ["胸"], ["腹"])))
            else:
                qty = 1
            return {"test": name, "item_id": row["item_id"], "item": row["item_cn"], "qty": qty,
                    "price": round(float(row["price_cny"]) * qty, 2), "status": row["status"]}
    return {"test": name, "item_id": None, "price": None, "status": "未匹配"}


def executed_tests(result):
    rejected = {log.get("test_name", "") for log in result.get("test_logs", [])
                if any(p in str(log.get("result", "")).lower() for p in REJECTION_PHRASES)}
    out = []
    for t in result.get("requested_tests_only", []):
        if t in rejected:
            continue
        out.append(re.sub(r"^test to order:\s*", "", t.strip(), flags=re.I))
    return out


def cost_result(result, rows, index):
    consult = next(float(r["price_cny"]) for r in rows if r["item_id"] == "V001")
    rounds = int(result.get("num_test_rounds", 0)) + 1
    details = [price_test(t, index) for t in executed_tests(result)]
    tests_total = sum(d["price"] or 0 for d in details)
    return {
        "case_id": result.get("case_id"), "k": result.get("k", 0),
        "num_rounds": rounds, "consult_fee_total": consult * rounds,
        "tests_total": round(tests_total, 2),
        "total_cny": round(tests_total + consult * rounds, 2),
        "unpriced": [d for d in details if d["price"] is None],
        "details": details,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_dir", nargs="?")
    ap.add_argument("--sheet", default=str(DEFAULT_SHEET))
    ap.add_argument("--out", default=None)
    ap.add_argument("--price", help="调试：给一个检查名，打印匹配结果")
    a = ap.parse_args()
    rows, index = load_sheet(a.sheet)
    if a.price:
        print(json.dumps(price_test(a.price, index), ensure_ascii=False, indent=2))
        return
    files = sorted(glob.glob(os.path.join(a.json_dir, "case_*.json")))
    costed = [cost_result(json.load(open(f, encoding="utf-8")), rows, index) for f in files]
    for c in costed:
        print(f"{c['case_id']} k{c['k']}: 合计 ¥{c['total_cny']:.1f}（检查 ¥{c['tests_total']:.1f} + 诊查 {c['num_rounds']}×）未计价 {len(c['unpriced'])} 项")
    if costed:
        avg = sum(c["total_cny"] for c in costed) / len(costed)
        print(f"平均每例 ¥{avg:.1f}；共 {len(costed)} 个结果")
    out = a.out or os.path.join(a.json_dir, "..", "cn-costv0.1.json")
    json.dump(costed, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
