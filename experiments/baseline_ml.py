import argparse
import asyncio
import csv
import json
import math
import os
import random
import time
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC

from app.core.taxonomy import DOCUMENT_TYPES
from app.services.llm_service import LLMService
from app.agents.classifier_agent import ClassifierAgent
from experiments.e1_classification import (
    compute_metrics_from_pairs,
    wilson_ci,
    bootstrap_ci,
    get_git_info
)
from experiments.baseline_rule import run_rule_baselines


def calc_boundary_tolerant_acc(preds: list[dict]) -> float:
    if not preds:
        return 0.0
    ok = sum(
        1 for p in preds
        if p["ground_truth"] == p["predicted"]
        or p.get("is_boundary_match")
        or (p["predicted"] in (p.get("secondary_candidates") or []))
    )
    return round(ok / len(preds), 4)


def to_pairs(preds: list[dict]) -> list[tuple[str, str]]:
    return [(p["ground_truth"], p["predicted"]) for p in preds]


def paired_bootstrap_diff(preds_ref: list[dict], preds_other: list[dict], class_codes: list[str], n_boot: int = 2000, seed: int = 42) -> dict:
    ref_map = {p["doc_id"]: p for p in preds_ref}
    other_map = {p["doc_id"]: p for p in preds_other}
    common_ids = sorted(list(set(ref_map.keys()) & set(other_map.keys())))
    
    if not common_ids:
        return {
            "delta_macro_f1": 0.0,
            "delta_macro_f1_ci95": [0.0, 0.0],
            "delta_acc": 0.0,
            "delta_acc_ci95": [0.0, 0.0],
            "p_boot": 1.0
        }

    sub_ref = [ref_map[did] for did in common_ids]
    sub_other = [other_map[did] for did in common_ids]

    ref_metrics = compute_metrics_from_pairs(to_pairs(sub_ref), class_codes)
    other_metrics = compute_metrics_from_pairs(to_pairs(sub_other), class_codes)

    obs_delta_f1 = ref_metrics["macro_f1"] - other_metrics["macro_f1"]
    obs_delta_acc = ref_metrics["accuracy"] - other_metrics["accuracy"]

    rng = random.Random(seed)
    diff_f1s = []
    diff_accs = []
    n = len(common_ids)

    for _ in range(n_boot):
        indices = [rng.randrange(n) for _ in range(n)]
        boot_ref = [sub_ref[i] for i in indices]
        boot_other = [sub_other[i] for i in indices]

        bm_ref = compute_metrics_from_pairs(to_pairs(boot_ref), class_codes)
        bm_other = compute_metrics_from_pairs(to_pairs(boot_other), class_codes)

        diff_f1s.append(bm_ref["macro_f1"] - bm_other["macro_f1"])
        diff_accs.append(bm_ref["accuracy"] - bm_other["accuracy"])

    diff_f1s.sort()
    diff_accs.sort()

    ci_f1_low = diff_f1s[int(0.025 * n_boot)]
    ci_f1_high = diff_f1s[int(0.975 * n_boot)]
    ci_acc_low = diff_accs[int(0.025 * n_boot)]
    ci_acc_high = diff_accs[int(0.975 * n_boot)]

    # İki yönlü bootstrap p-değeri (null hipotezi delta_macro_f1 == 0)
    p_le = sum(1 for d in diff_f1s if d <= 0.0) / n_boot
    p_ge = sum(1 for d in diff_f1s if d >= 0.0) / n_boot
    p_boot = min(1.0, 2.0 * min(p_le, p_ge))

    return {
        "delta_macro_f1": float(obs_delta_f1),
        "delta_macro_f1_ci95": [float(ci_f1_low), float(ci_f1_high)],
        "delta_acc": float(obs_delta_acc),
        "delta_acc_ci95": [float(ci_acc_low), float(ci_acc_high)],
        "p_boot": float(p_boot)
    }


def mcnemar_test(preds_ref: list[dict], preds_other: list[dict]) -> dict:
    ref_map = {p["doc_id"]: p for p in preds_ref}
    other_map = {p["doc_id"]: p for p in preds_other}
    common_ids = sorted(list(set(ref_map.keys()) & set(other_map.keys())))

    b = 0  # ref doğru, other yanlış
    c = 0  # ref yanlış, other doğru

    for did in common_ids:
        r_item = ref_map[did]
        o_item = other_map[did]
        
        r_correct = (r_item["predicted"] == r_item["ground_truth"])
        o_correct = (o_item["predicted"] == o_item["ground_truth"])

        if r_correct and not o_correct:
            b += 1
        elif not r_correct and o_correct:
            c += 1

    total_discordant = b + c
    if total_discordant > 0:
        res = stats.binomtest(min(b, c), total_discordant, 0.5)
        p_val = float(res.pvalue)
    else:
        p_val = 1.0

    return {
        "b": int(b),
        "c": int(c),
        "discordant": int(total_discordant),
        "p_value": float(p_val)
    }


def run_ml_baselines() -> dict:
    dev_path = os.path.join("data", "eval", "classification", "dev.json")
    test_path = os.path.join("data", "eval", "classification", "test.json")

    with open(dev_path, "r", encoding="utf-8") as f:
        dev_data = json.load(f)
    with open(test_path, "r", encoding="utf-8") as f:
        test_data = json.load(f)

    def extract_text(record):
        title = record.get("title", "") or ""
        content = record.get("content", "") or ""
        return f"{title}\n\n{content[:3000]}".strip()

    X_dev = [extract_text(r) for r in dev_data]
    y_dev = [r.get("ground_truth") or r.get("document_type") or r.get("true_type") or r.get("label") for r in dev_data]

    X_test = [extract_text(r) for r in test_data]
    doc_ids = [r.get("doc_id", f"test_{i}") for i, r in enumerate(test_data)]

    class_codes = [dt.code for dt in DOCUMENT_TYPES]

    feature_union = FeatureUnion([
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), max_features=15000, sublinear_tf=True)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=25000, sublinear_tf=True))
    ])

    models = {
        "tfidf_logreg": LogisticRegression(C=2.0, max_iter=1000, random_state=42),
        "tfidf_linearsvc": LinearSVC(C=1.0, random_state=42)
    }

    results = {}

    for name, clf in models.items():
        pipeline = Pipeline([
            ("features", feature_union),
            ("clf", clf)
        ])

        start_time = time.time()
        pipeline.fit(X_dev, y_dev)
        train_time = time.time() - start_time

        t_start = time.time()
        preds = pipeline.predict(X_test)
        total_inf_time = time.time() - t_start
        mean_latency = (total_inf_time / len(X_test)) * 1000.0

        pred_pairs = []
        for i, (did, r, pred_val) in enumerate(zip(doc_ids, test_data, preds)):
            true_val = r.get("ground_truth") or r.get("document_type") or r.get("true_type") or r.get("label")
            sec_cands = r.get("secondary_candidates", [])
            pred_pairs.append({
                "doc_id": did,
                "ground_truth": true_val,
                "predicted": pred_val,
                "secondary_candidates": sec_cands,
                "is_boundary_match": (pred_val in sec_cands),
                "latency_ms": round(mean_latency, 4)
            })

        metrics = compute_metrics_from_pairs(to_pairs(pred_pairs), class_codes)
        correct_count = sum(1 for p in pred_pairs if p["ground_truth"] == p["predicted"])
        w_ci = wilson_ci(correct_count, len(pred_pairs))
        b_ci = bootstrap_ci(pred_pairs, class_codes, n_boot=2000, seed=42)

        results[name] = {
            "metrics": metrics,
            "wilson_ci": w_ci,
            "bootstrap_ci": b_ci,
            "predictions": pred_pairs,
            "train_time_sec": train_time,
            "mean_latency_ms": mean_latency
        }

    return results


async def run_alt_llm_baseline(model_name: str = "qwen3:8b", fresh: bool = False) -> tuple[dict, list[dict]]:
    test_path = os.path.join("data", "eval", "classification", "test.json")
    with open(test_path, "r", encoding="utf-8") as f:
        test_data = json.load(f)

    os.makedirs(os.path.join("results", "e2"), exist_ok=True)
    chk_path = os.path.join("results", "e2", "qwen3_8b_preds.json")

    existing_preds = {}
    if not fresh and os.path.exists(chk_path):
        try:
            with open(chk_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for p in saved:
                    existing_preds[p["doc_id"]] = p
            print(f"[Qwen3 Baseline] Mevcut checkpoint yüklendi: {len(existing_preds)} kayıt bulundu.")
        except Exception:
            pass

    llm = LLMService()
    llm.model = model_name
    classifier = ClassifierAgent(llm_service=llm)

    class_codes = [dt.code for dt in DOCUMENT_TYPES]
    preds = []
    total = len(test_data)

    for idx, record in enumerate(test_data, 1):
        did = record.get("doc_id", f"test_{idx}")
        if did in existing_preds:
            preds.append(existing_preds[did])
            continue

        title = record.get("title", "") or ""
        content = record.get("content", "") or ""
        text_input = f"{title}\n\n{content[:3000]}".strip()
        true_val = record.get("ground_truth") or record.get("document_type") or record.get("true_type") or record.get("label")
        sec_cands = record.get("secondary_candidates", [])

        if hasattr(llm, "_cache") and llm._cache is not None:
            llm._cache.clear()

        t0 = time.time()
        try:
            res = await classifier.execute(text_input)
            pred_code = getattr(res, "document_type", None) or res.get("document_type") or res.get("code") or "OTHER"
            conf = getattr(res, "confidence", 1.0)
            reas = getattr(res, "reasoning", "")
        except Exception as e:
            print(f"Hata ({did}): {e}")
            pred_code = "OTHER"
            conf = 0.0
            reas = str(e)
        lat = (time.time() - t0) * 1000.0

        item = {
            "doc_id": did,
            "ground_truth": true_val,
            "predicted": pred_code,
            "confidence": conf,
            "secondary_candidates": sec_cands,
            "is_boundary_match": (pred_code in sec_cands),
            "reasoning": reas,
            "latency_ms": round(lat, 2)
        }
        preds.append(item)
        existing_preds[did] = item

        print(f"[{idx}/{total}] doc_id={did} | GT={true_val} Pred={pred_code} ({lat:.1f}ms)")

        if idx % 10 == 0:
            with open(chk_path, "w", encoding="utf-8") as f:
                json.dump(preds, f, ensure_ascii=False, indent=2)

    await llm.close()

    with open(chk_path, "w", encoding="utf-8") as f:
        json.dump(preds, f, ensure_ascii=False, indent=2)

    metrics = compute_metrics_from_pairs(to_pairs(preds), class_codes)
    correct_count = sum(1 for p in preds if p["ground_truth"] == p["predicted"])
    w_ci = wilson_ci(correct_count, len(preds))
    b_ci = bootstrap_ci(preds, class_codes, n_boot=2000, seed=42)
    mean_lat = round(sum(p["latency_ms"] for p in preds) / max(1, len(preds)), 2)

    return {
        "metrics": metrics,
        "wilson_ci": w_ci,
        "bootstrap_ci": b_ci,
        "predictions": preds,
        "mean_latency_ms": mean_lat
    }, preds


async def run_e2_all(skip_alt_llm: bool = False, fresh_llm: bool = False):
    os.makedirs(os.path.join("results", "e2"), exist_ok=True)
    class_codes = [dt.code for dt in DOCUMENT_TYPES]

    print("--- Faz 5 (E2): Rule Baselines Çalıştırılıyor ---")
    rule_results = run_rule_baselines("test")
    rule_preds_path = os.path.join("results", "e2", "baseline_rule_predictions.json")
    rule_keywords_preds = []
    rule_header_preds = []
    if os.path.exists(rule_preds_path):
        with open(rule_preds_path, "r", encoding="utf-8") as f:
            rule_preds_data = json.load(f)
            rule_keywords_preds = rule_preds_data.get("predictions_a1", [])
            rule_header_preds = rule_preds_data.get("predictions_a2", [])
    else:
        rule_keywords_preds = rule_results.get("baseline_a1_taxonomy_keywords", {}).get("predictions", [])
        rule_header_preds = rule_results.get("baseline_a2_structural_rules", {}).get("predictions", [])

    print("--- Faz 5 (E2): Klasik ML Baselines Çalıştırılıyor ---")
    ml_results = run_ml_baselines()
    logreg_res = ml_results["tfidf_logreg"]
    linearsvc_res = ml_results["tfidf_linearsvc"]

    qwen_res = None
    qwen_preds = []
    if not skip_alt_llm:
        print("--- Faz 5 (E2): Alternatif LLM (Qwen3:8b) Baseline Çalıştırılıyor ---")
        qwen_summary, qwen_preds = await run_alt_llm_baseline("qwen3:8b", fresh=fresh_llm)
        qwen_res = qwen_summary
    else:
        qwen_chk = os.path.join("results", "e2", "qwen3_8b_preds.json")
        if os.path.exists(qwen_chk):
            with open(qwen_chk, "r", encoding="utf-8") as f:
                qwen_preds = json.load(f)
            qwen_metrics = compute_metrics_from_pairs(to_pairs(qwen_preds), class_codes)
            correct_count = sum(1 for p in qwen_preds if p["ground_truth"] == p["predicted"])
            qwen_res = {
                "metrics": qwen_metrics,
                "wilson_ci": wilson_ci(correct_count, len(qwen_preds)),
                "bootstrap_ci": bootstrap_ci(qwen_preds, class_codes, n_boot=2000, seed=42),
                "predictions": qwen_preds,
                "mean_latency_ms": round(sum(p["latency_ms"] for p in qwen_preds) / max(1, len(qwen_preds)), 2)
            }

    print("--- Faz 5 (E2): Referans Gemma (e1) Yükleniyor ---")
    e1_preds_path = os.path.join("results", "e1", "predictions.json")
    gemma_preds = []
    if os.path.exists(e1_preds_path):
        with open(e1_preds_path, "r", encoding="utf-8") as f:
            gemma_preds = json.load(f)
    
    gemma_metrics = compute_metrics_from_pairs(to_pairs(gemma_preds), class_codes)
    gemma_correct = sum(1 for p in gemma_preds if p["ground_truth"] == p["predicted"])
    gemma_res = {
        "metrics": gemma_metrics,
        "wilson_ci": wilson_ci(gemma_correct, len(gemma_preds)),
        "bootstrap_ci": bootstrap_ci(gemma_preds, class_codes, n_boot=2000, seed=42),
        "predictions": gemma_preds,
        "mean_latency_ms": round(sum(p.get("latency_ms", 0) for p in gemma_preds) / max(1, len(gemma_preds)), 2)
    }

    r_a1 = rule_results.get("baseline_a1_taxonomy_keywords", {})
    r_a2 = rule_results.get("baseline_a2_structural_rules", {})

    all_methods = {
        "baseline_a1_taxonomy_keywords": {
            "name": "Kural Tabanlı (Keywords)",
            "predictions": rule_keywords_preds,
            "metrics": r_a1.get("metrics", compute_metrics_from_pairs(to_pairs(rule_keywords_preds), class_codes)),
            "bootstrap_ci": r_a1.get("bootstrap_ci", bootstrap_ci(rule_keywords_preds, class_codes, n_boot=2000, seed=42)),
            "mean_latency_ms": r_a1.get("mean_latency_ms", 0.0)
        },
        "baseline_a2_structural_rules": {
            "name": "Kural Tabanlı (Header/Structural)",
            "predictions": rule_header_preds,
            "metrics": r_a2.get("metrics", compute_metrics_from_pairs(to_pairs(rule_header_preds), class_codes)),
            "bootstrap_ci": r_a2.get("bootstrap_ci", bootstrap_ci(rule_header_preds, class_codes, n_boot=2000, seed=42)),
            "mean_latency_ms": r_a2.get("mean_latency_ms", 0.0)
        },
        "tfidf_logreg": {
            "name": "TF-IDF + Logistic Regression",
            "predictions": logreg_res["predictions"],
            "metrics": logreg_res["metrics"],
            "bootstrap_ci": logreg_res["bootstrap_ci"],
            "mean_latency_ms": logreg_res["mean_latency_ms"]
        },
        "tfidf_linearsvc": {
            "name": "TF-IDF + LinearSVC",
            "predictions": linearsvc_res["predictions"],
            "metrics": linearsvc_res["metrics"],
            "bootstrap_ci": linearsvc_res["bootstrap_ci"],
            "mean_latency_ms": linearsvc_res["mean_latency_ms"]
        },
    }

    if qwen_res:
        all_methods["qwen3_8b"] = {
            "name": "Qwen3:8b (Alternatif LLM)",
            "predictions": qwen_res["predictions"],
            "metrics": qwen_res["metrics"],
            "bootstrap_ci": qwen_res["bootstrap_ci"],
            "mean_latency_ms": qwen_res["mean_latency_ms"]
        }

    all_methods["gemma4_12b"] = {
        "name": "Gemma 4:12b (Referans)",
        "predictions": gemma_preds,
        "metrics": gemma_metrics,
        "bootstrap_ci": gemma_res["bootstrap_ci"],
        "mean_latency_ms": gemma_res["mean_latency_ms"]
    }

    csv_path = os.path.join("results", "e2", "baselines_comparison.csv")
    json_path = os.path.join("results", "e2", "baselines_comparison.json")
    png_path = os.path.join("results", "e2", "baselines_comparison.png")
    md_path = os.path.join("results", "e2", "e2_analysis.md")

    summary_json_data = {}
    csv_rows = []

    for key, data in all_methods.items():
        m = data["metrics"]
        bci = data["bootstrap_ci"]
        preds_list = data["predictions"]
        correct_cnt = sum(1 for p in preds_list if p["ground_truth"] == p["predicted"])
        w_ci = wilson_ci(correct_cnt, len(preds_list))

        summary_json_data[key] = {
            "method_name": data["name"],
            "accuracy": m.get("accuracy"),
            "macro_f1": m.get("macro_f1"),
            "weighted_f1": m.get("weighted_f1"),
            "boundary_tolerant_acc": calc_boundary_tolerant_acc(preds_list),
            "wilson_ci": w_ci,
            "mean_latency_ms": data.get("mean_latency_ms", 0.0),
            "macro_f1_ci": bci.get("macro_f1_ci", [0.0, 0.0]),
            "accuracy_ci": bci.get("accuracy_ci", [0.0, 0.0])
        }
        csv_rows.append({
            "method_key": key,
            "method_name": data["name"],
            "accuracy": m.get("accuracy"),
            "macro_f1": m.get("macro_f1"),
            "weighted_f1": m.get("weighted_f1"),
            "boundary_tolerant_acc": calc_boundary_tolerant_acc(preds_list),
            "mean_latency_ms": data.get("mean_latency_ms", 0.0)
        })

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary_json_data, f, ensure_ascii=False, indent=2)

    if csv_rows:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
            writer.writeheader()
            writer.writerows(csv_rows)

    names = [d["method_name"] for d in csv_rows]
    f1s = [d["macro_f1"] for d in csv_rows]
    accs = [d["accuracy"] for d in csv_rows]

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(names))
    width = 0.35

    ax.bar(x - width/2, f1s, width, label="Macro-F1", color="#4C72B0")
    ax.bar(x + width/2, accs, width, label="Accuracy", color="#DD8452")

    ax.set_ylabel("Skor")
    ax.set_title("E2: Baseline ve Model Karşılaştırmaları (Macro-F1 & Accuracy)")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=25, ha="right")
    ax.set_ylim(0, 1.05)
    ax.legend()
    fig.tight_layout()
    plt.savefig(png_path, dpi=300)
    plt.close()

    ref_key = "gemma4_12b" if "gemma4_12b" in all_methods else list(all_methods.keys())[-1]
    ref_preds = all_methods[ref_key]["predictions"]

    stats_comparisons = {}
    for key, data in all_methods.items():
        if key == ref_key:
            continue
        other_preds = data["predictions"]
        boot_diff = paired_bootstrap_diff(ref_preds, other_preds, class_codes, n_boot=2000)
        mcnemar = mcnemar_test(ref_preds, other_preds)
        stats_comparisons[key] = {
            "bootstrap_diff": boot_diff,
            "mcnemar": mcnemar
        }

    md_content = []
    md_content.append("# Faz 5 (Deney E2): Baseline ve Model Karşılaştırma Raporu\n")
    md_content.append(f"**Tarih:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    git_info = get_git_info()
    if git_info:
        md_content.append(f"**Git Commit:** `{git_info.get('commit', 'Bilinmiyor')}` ({git_info.get('branch', '')})\n")
    
    md_content.append("\n## 1. Genel Performans Tablosu\n")
    md_content.append("| Yöntem | Doğruluk (Accuracy) | Macro-F1 | Weighted-F1 | Sınır Toleranslı Doğruluk |")
    md_content.append("|---|---|---|---|---|")
    for r in csv_rows:
        md_content.append(f"| {r['method_name']} | {r['accuracy']:.4f} | {r['macro_f1']:.4f} | {r['weighted_f1']:.4f} | {r['boundary_tolerant_acc']:.4f} |")

    md_content.append(f"\n## 2. İstatistiksel Karşılaştırma (Referans: {all_methods[ref_key]['name']})\n")
    md_content.append("| Karşılaştırılan Yöntem | Delta Macro-F1 (%95 GA) | Delta Acc (%95 GA) | Bootstrap p | McNemar p |")
    md_content.append("|---|---|---|---|---|")
    for key, st_data in stats_comparisons.items():
        m_name = all_methods[key]["name"]
        bd = st_data["bootstrap_diff"]
        mc = st_data["mcnemar"]
        f1_ci = f"[{bd['delta_macro_f1_ci95'][0]:.4f}, {bd['delta_macro_f1_ci95'][1]:.4f}]"
        acc_ci = f"[{bd['delta_acc_ci95'][0]:.4f}, {bd['delta_acc_ci95'][1]:.4f}]"
        md_content.append(f"| {m_name} | {bd['delta_macro_f1']:.4f} {f1_ci} | {bd['delta_acc']:.4f} {acc_ci} | {bd['p_boot']:.4f} | {mc['p_value']:.4f} |")

    md_content.append("\n## 3. Sınıf Bazında F1 Karşılaştırma Tablosu\n")
    header_cols = ["Sınıf Kod"] + [d["name"] for d in all_methods.values()]
    md_content.append("| " + " | ".join(header_cols) + " |")
    md_content.append("| " + " | ".join(["---"] * len(header_cols)) + " |")

    for code in class_codes:
        row_cells = [code]
        for key, data in all_methods.items():
            classes_dict = data["metrics"].get("classes", {})
            cls_metrics = classes_dict.get(code, {})
            f1_val = cls_metrics.get("f1", 0.0)
            row_cells.append(f"{f1_val:.4f}")
        md_content.append("| " + " | ".join(row_cells) + " |")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_content))

    print(f"--- E2 Çalışması Tamamlandı. Sonuçlar kaydedildi: {os.path.join('results', 'e2')} ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Faz 5: Deney E2 Baseline Karşılaştırmaları")
    parser.add_argument("--skip-alt-llm", action="store_true", help="Alternatif LLM (Qwen3) çalıştırmasını atla")
    parser.add_argument("--fresh-llm", action="store_true", help="Önbelleği/checkpoint'i yok sayarak LLM testini sıfırdan çalıştır")
    args = parser.parse_args()

    asyncio.run(run_e2_all(skip_alt_llm=args.skip_alt_llm, fresh_llm=args.fresh_llm))
