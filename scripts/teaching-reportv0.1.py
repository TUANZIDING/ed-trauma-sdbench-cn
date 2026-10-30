#!/usr/bin/env python3
"""教学模式反馈报告：把一次诊断会话（AI 或学员）转为中文反馈报告（Markdown）。
Generate a Chinese feedback report for one sequential-diagnosis session (AI or trainee).

输入 / Input
  - 一个 SDBench 结果 JSON（harness 输出的 case_k*_<id>.json），或学员会话日志（同样字段，
    另加可选 learner、started_at、finished_at，ISO 时间）。
  - data/processed_case_data/ed-trauma-cn/case-metav0.1.json（关键检查、鉴别、线索、指南）。
  - costing/cn-cost-sheetv0.1.csv（通过 cn-costingv0.1.py 计价）。

记录指标 / Metrics: 提问数、检查数、费用（人民币）、用时、诊断得分（Judge 1–5，≥4 视为正确）、
  关键检查覆盖率、未执行的关键检查、可能的过度检查（不在关键清单且费用 ≥200 元）。

用法 / Usage
  python scripts/teaching-reportv0.1.py <session.json> [--out report.md]
"""
import argparse
import datetime as dt
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
META = ROOT / "data" / "processed_case_data" / "ed-trauma-cn" / "case-metav0.1.json"
spec = importlib.util.spec_from_file_location("cncost", ROOT / "scripts" / "cn-costingv0.1.py")
cncost = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cncost)

SCORE_TEXT = {5: "完全正确", 4: "基本正确（主要诊断命中）", 3: "部分正确", 2: "大方向相关但关键错误", 1: "错误"}


LIMB_WORDS = ["骨盆", "髋", "股骨", "下肢", "上肢", "胫", "腓", "锁骨", "肋", "椎"]


def signature(name, index):
    """检查的比对签名：项目编号 + 部位关键词（区分胸片与骨盆片、头颅CT与腹部CT）。"""
    item = cncost.price_test(name, index).get("item_id")
    n = name.lower()
    regions = frozenset(k for k, ws in cncost.REGION_WORDS.items() if any(w in n for w in ws))
    regions |= frozenset(w for w in LIMB_WORDS if w in n)
    if item in {"I001", "I003", "I004", "I005", "I006", "I007"}:
        return (item, regions)
    return (item, frozenset())


def covered(key, done_sigs):
    item, regs = key
    return any(i == item and (not regs or regs & r) for i, r in done_sigs)


def minutes(a, b):
    try:
        return round((dt.datetime.fromisoformat(b) - dt.datetime.fromisoformat(a)).total_seconds() / 60, 1)
    except Exception:
        return None


def build(result, meta, rows, index):
    cid = str(result["case_id"])
    m = meta.get(cid, {})
    cost = cncost.cost_result(result, rows, index)
    questions = [t for t in result.get("requested_tests", []) if t.lower().startswith(cncost.QUESTION_PREFIX)]
    tests = cost["details"]
    keys = [(k, signature(k, index)) for k in m.get("key_tests", [])]
    done_sigs = [signature(d["test"], index) for d in tests]
    missed = [k for k, sig in keys if not covered(sig, done_sigs)]
    key_sigs = [sig for _, sig in keys]
    extra = [d for d in tests if not covered(signature(d["test"], index), key_sigs) and (d.get("price") or 0) >= 200]
    cover = (1 - len(missed) / len(keys)) if keys else None
    score = result.get("diagnosis_score")
    mins = minutes(result.get("started_at", ""), result.get("finished_at", ""))

    L = [f"# 序贯诊断反馈报告：{result.get('case_title', cid)}", ""]
    L += [f"- 学员 / 模型：{result.get('learner') or result.get('model', '未注明')}",
          f"- 病例主题：{m.get('topic', '')}（难度：{m.get('difficulty', '')}）", ""]
    L += ["## 一、总览", "", "| 指标 | 结果 |", "|---|---|",
          f"| 诊断得分 | {score if score is not None else '未评分'} / 5 {('— ' + SCORE_TEXT.get(score, '')) if score else ''} |",
          f"| 是否正确（≥4） | {'是' if result.get('correct') else '否'} |",
          f"| 提问数 | {len(questions)} |",
          f"| 检查数（已执行） | {len(tests)} |",
          f"| 问诊/检查轮数 | {cost['num_rounds']} |",
          f"| 估算费用 | ¥{cost['total_cny']:.1f}（检查 ¥{cost['tests_total']:.1f} + 诊查费 ¥{cost['consult_fee_total']:.0f}） |",
          f"| 用时 | {str(mins) + ' 分钟' if mins is not None else '未记录'} |",
          f"| 关键检查覆盖率 | {f'{cover:.0%}' if cover is not None else '—'} |", ""]
    L += ["## 二、你的诊断 vs 参考诊断", "",
          f"- 你的诊断：{result.get('model_diagnosis', '')}",
          f"- 参考诊断：{m.get('final_diagnosis', result.get('actual_diagnosis', ''))}"]
    if result.get("diagnosis_reasoning"):
        L.append(f"- 评分理由：{result['diagnosis_reasoning']}")
    L += ["", "## 三、检查与费用明细", "", "| 检查 | 匹配项目 | 费用 | 状态 |", "|---|---|---|---|"]
    for d in tests:
        price = f"¥{d['price']:.1f}" if d.get("price") is not None else "—"
        L.append(f"| {d['test']} | {d.get('item', '')} | {price} | {d['status']} |")
    if cost["unpriced"]:
        L.append(f"\n> {len(cost['unpriced'])} 项未计价（价格待核实或未匹配），合计费用偏低。")
    L += ["", "## 四、教学反馈", ""]
    L.append("**遗漏的关键检查：** " + ("、".join(missed) if missed else "无"))
    L.append("")
    L.append("**可能的高费用非关键检查（≥200 元，请反思是否必要）：** "
             + ("、".join(f"{d['test']}（¥{d['price']:.0f}）" for d in extra) if extra else "无"))
    L += ["", "**本例关键线索：**"] + [f"- {x}" for x in m.get("key_clues", [])]
    L += ["", "**应考虑的鉴别诊断：**"] + [f"- {x}" for x in m.get("key_differentials", [])]
    L += ["", "**延伸阅读（指南）：**"] + [f"- {x}" for x in m.get("guideline_refs", [])]
    L += ["", "---", "本报告由 ed-trauma-sdbench-cn v0.1 生成，费用为江苏/无锡公立医院公开价格估算，仅供教学与研究，不代表实际收费，不作临床决策依据。"]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--out")
    a = ap.parse_args()
    result = json.load(open(a.session, encoding="utf-8"))
    meta = json.load(open(META, encoding="utf-8"))
    rows, index = cncost.load_sheet(cncost.DEFAULT_SHEET)
    md = build(result, meta, rows, index)
    if a.out:
        pathlib.Path(a.out).write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
