import argparse
import asyncio
import csv
import hashlib
import json
import math
import os
import random
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from app.config import get_settings
from app.core.taxonomy import DOCUMENT_TYPES
from app.services.llm_service import LLMService
from app.agents.classifier_agent import ClassifierAgent


def get_git_info() -> dict:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode("utf-8").strip()
        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL).decode("utf-8").strip()
        return {"commit": commit, "branch": branch}
    except Exception:
        return {"commit": "unknown", "branch": "unknown"}


def sha256_file(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def wilson_ci(k: int, n: int, z: float = 1.95996) -> list[float]:
    if n == 0:
        return [0.0, 0.0]
    p_hat = k / n
    denom = 1.0 + (z**2) / n
    center = (p_hat + (z**2) / (2 * n)) / denom
    margin = (z * math.sqrt((p_hat * (1 - p_hat) / n) + (z**2) / (4 * n**2))) / denom
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return [round(lower, 4), round(upper, 4)]


def compute_metrics_from_pairs(pairs: list[tuple[str, str]], class_codes: list[str]) -> dict:
    y_true = [p[0] for p in pairs]
    y_pred = [p[1] for p in pairs]
    total = len(pairs)
    
    stats = {c: {"tp": 0, "fp": 0, "fn": 0, "support": 0} for c in class_codes}
    
    for true_c, pred_c in zip(y_true, y_pred):
        if true_c in stats:
            stats[true_c]["support"] += 1
        if true_c == pred_c:
            if true_c in stats:
                stats[true_c]["tp"] += 1
        else:
            if pred_c in stats:
                stats[pred_c]["fp"] += 1
            if true_c in stats:
                stats[true_c]["fn"] += 1

    class_metrics = {}
    macro_p = 0.0
    macro_r = 0.0
    macro_f1 = 0.0
    weighted_p = 0.0
    weighted_r = 0.0
    weighted_f1 = 0.0
    
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    accuracy = correct / total if total > 0 else 0.0

    valid_classes = 0
    for c in class_codes:
        s = stats[c]
        tp = s["tp"]
        fp = s["fp"]
        fn = s["fn"]
        support = s["support"]
        
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        
        class_metrics[c] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "support": support,
            "tp": tp,
            "fp": fp,
            "fn": fn
        }
        
        if support > 0:
            valid_classes += 1
            macro_p += prec
            macro_r += rec
            macro_f1 += f1
            weighted_p += prec * support
            weighted_r += rec * support
            weighted_f1 += f1 * support

    if valid_classes > 0:
        macro_p /= valid_classes
        macro_r /= valid_classes
        macro_f1 /= valid_classes

    if total > 0:
        weighted_p /= total
        weighted_r /= total
        weighted_f1 /= total

    micro_f1 = accuracy

    return {
        "accuracy": round(accuracy, 4),
        "macro_precision": round(macro_p, 4),
        "macro_recall": round(macro_r, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_precision": round(weighted_p, 4),
        "weighted_recall": round(weighted_r, 4),
        "weighted_f1": round(weighted_f1, 4),
        "micro_f1": round(micro_f1, 4),
        "classes": class_metrics,
        "total_samples": total
    }


def bootstrap_ci(predictions: list[dict], class_codes: list[str], n_boot: int = 2000, seed: int = 42) -> dict:
    rng = random.Random(seed)
    n = len(predictions)
    if n == 0:
        return {}

    pairs = [(p["ground_truth"], p["predicted"]) for p in predictions]
    
    boot_accs = []
    boot_macro_f1s = []
    boot_weighted_f1s = []
    boot_class_f1s = {c: [] for c in class_codes}

    for _ in range(n_boot):
        sample_pairs = rng.choices(pairs, k=n)
        metrics = compute_metrics_from_pairs(sample_pairs, class_codes)
        boot_accs.append(metrics["accuracy"])
        boot_macro_f1s.append(metrics["macro_f1"])
        boot_weighted_f1s.append(metrics["weighted_f1"])
        for c in class_codes:
            boot_class_f1s[c].append(metrics["classes"][c]["f1"])

    def get_pct(arr):
        return [round(float(np.percentile(arr, 2.5)), 4), round(float(np.percentile(arr, 97.5)), 4)]

    res = {
        "accuracy_ci": get_pct(boot_accs),
        "macro_f1_ci": get_pct(boot_macro_f1s),
        "weighted_f1_ci": get_pct(boot_weighted_f1s),
        "classes": {}
    }
    for c in class_codes:
        res["classes"][c] = {"f1_ci": get_pct(boot_class_f1s[c])}

    return res


def save_confusion_matrix(predictions: list[dict], class_codes: list[str], out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    n_classes = len(class_codes)
    code_to_idx = {c: i for i, c in enumerate(class_codes)}
    
    matrix = np.zeros((n_classes, n_classes), dtype=int)
    for p in predictions:
        gt = p["ground_truth"]
        pred = p["predicted"]
        if gt in code_to_idx and pred in code_to_idx:
            matrix[code_to_idx[gt]][code_to_idx[pred]] += 1

    csv_path = os.path.join(out_dir, "confusion_matrix.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ground_truth \\ predicted"] + class_codes)
        for i, c in enumerate(class_codes):
            writer.writerow([c] + list(matrix[i]))

    plt.figure(figsize=(14, 11))
    sns.heatmap(matrix, annot=True, fmt="d", cmap="Blues", xticklabels=class_codes, yticklabels=class_codes)
    plt.xlabel("Tahmin Edilen (Predicted)")
    plt.ylabel("Gerçek (Ground Truth)")
    plt.title("Sınıflandırma Karmaşıklık Matrisi (Confusion Matrix)")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "confusion_matrix.png"), dpi=300)
    plt.close()


def save_error_analysis(predictions: list[dict], metrics: dict, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    
    errors = [p for p in predictions if p["ground_truth"] != p["predicted"]]
    
    csv_path = os.path.join(out_dir, "error_examples.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "doc_id", "ground_truth", "predicted", "confidence",
            "origin_type", "secondary_candidates", "is_boundary_match", "title", "reasoning"
        ])
        for e in errors:
            writer.writerow([
                e.get("doc_id"),
                e.get("ground_truth"),
                e.get("predicted"),
                e.get("confidence"),
                e.get("origin_type"),
                json.dumps(e.get("secondary_candidates", []), ensure_ascii=False),
                e.get("is_boundary_match"),
                e.get("title"),
                e.get("reasoning")
            ])

    confused_pairs = defaultdict(int)
    for e in errors:
        confused_pairs[(e["ground_truth"], e["predicted"])] += 1
    top_confused = sorted(confused_pairs.items(), key=lambda x: x[1], reverse=True)[:10]

    ci_classes = metrics.get("bootstrap_ci", {}).get("classes", {})
    acc_ci = metrics.get("wilson_95_ci", [])

    md_path = os.path.join(out_dir, "error_analysis.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# E1 Sınıflandırma Deneyi - Hata Analizi ve Raporu\n\n")
        f.write(f"**Tarih:** {datetime.now().isoformat()}\n\n")
        f.write(f"**Toplam Örnek:** {metrics['total_samples']}\n")
        f.write(f"**Doğruluk (Accuracy):** {metrics['accuracy']} (Wilson 95% CI: {acc_ci})\n")
        f.write(f"**Macro F1:** {metrics['macro_f1']}\n")
        f.write(f"**Weighted F1:** {metrics['weighted_f1']}\n\n")

        f.write("## En Sık Karışan Sınıf Çiftleri (Top Confused Pairs)\n\n")
        f.write("| Gerçek Sınıf (Ground Truth) | Tahmin Edilen Sınıf (Predicted) | Hata Sayısı |\n")
        f.write("|---|---|---|\n")
        for (gt, pred), count in top_confused:
            f.write(f"| {gt} | {pred} | {count} |\n")
        f.write("\n")

        f.write("## Sınıf Bazlı Metrikler Tablosu\n\n")
        f.write("| Sınıf Kodu | Precision | Recall | F1-Score | F1 95% CI | Support |\n")
        f.write("|---|---|---|---|---|---|\n")
        for c, m in metrics["classes"].items():
            c_ci = ci_classes.get(c, {}).get("f1_ci", [0.0, 0.0])
            f.write(f"| {c} | {m['precision']} | {m['recall']} | {m['f1']} | {c_ci} | {m['support']} |\n")
        f.write("\n")


async def run_experiment(dataset_split: str = "test", fresh: bool = False, limit: int = 0):
    dataset_path = os.path.join("data", "eval", "classification", f"{dataset_split}.json")
    out_dir = os.path.join("results", "e1")
    os.makedirs(out_dir, exist_ok=True)
    
    pred_json_path = os.path.join(out_dir, "predictions.json")
    
    if not os.path.exists(dataset_path):
        print(f"Hata: Veri seti bulunamadı: {dataset_path}")
        return

    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    if limit > 0:
        dataset = dataset[:limit]

    completed = {}
    if not fresh and os.path.exists(pred_json_path):
        try:
            with open(pred_json_path, "r", encoding="utf-8") as f:
                existing_preds = json.load(f)
                for p in existing_preds:
                    completed[p["doc_id"]] = p
            print(f"Mevcut {len(completed)} tahmin yüklendi, kaldığı yerden devam ediliyor...")
        except Exception:
            pass

    class_codes = DOCUMENT_TYPES.codes()
    
    llm = LLMService()
    classifier = ClassifierAgent(llm_service=llm)

    predictions = list(completed.values())
    completed_ids = set(completed.keys())

    print(f"Toplam {len(dataset)} örnek işlenecek.")
    
    for item in dataset:
        doc_id = item.get("doc_id") or item.get("id") or sha256_text(item.get("content", ""))
        if doc_id in completed_ids:
            continue

        title = item.get("title", "")
        content = item.get("content", "")
        ground_truth = item.get("document_type") or item.get("ground_truth") or item.get("category", "")
        secondary_candidates = item.get("secondary_candidates", [])
        origin_type = item.get("origin_type", "unknown")
        length_bucket = item.get("length_bucket", "unknown")
        legal_status = item.get("legal_status", "unknown")

        text_input = f"{title}\n\n{content}".strip()
        
        if hasattr(llm, "_cache") and hasattr(llm._cache, "clear"):
            llm._cache.clear()

        t0 = time.perf_counter()
        try:
            res = await classifier.execute(text_input)
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            
            predicted = res.document_type
            confidence = res.confidence
            sub_type = res.sub_type
            reasoning = res.reasoning
            correct = (predicted == ground_truth)
            is_boundary_match = (predicted in secondary_candidates)
        except Exception as e:
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            predicted = "ERROR"
            confidence = 0.0
            sub_type = ""
            reasoning = str(e)
            correct = False
            is_boundary_match = False

        pred_record = {
            "doc_id": doc_id,
            "title": title,
            "ground_truth": ground_truth,
            "predicted": predicted,
            "confidence": confidence,
            "sub_type": sub_type,
            "origin_type": origin_type,
            "length_bucket": length_bucket,
            "legal_status": legal_status,
            "secondary_candidates": secondary_candidates,
            "is_boundary_match": is_boundary_match,
            "reasoning": reasoning,
            "latency_ms": latency_ms
        }
        
        predictions.append(pred_record)
        completed_ids.add(doc_id)

        print(f"[{len(predictions)}/{len(dataset)}] {doc_id} | GT={ground_truth:<15} Pred={predicted:<15} {'OK' if correct else 'ERR'} ({latency_ms:.0f} ms)", flush=True)

        if len(predictions) % 10 == 0:
            with open(pred_json_path, "w", encoding="utf-8") as f:
                json.dump(predictions, f, ensure_ascii=False, indent=2)

    await llm.close()

    # Final save of predictions
    with open(pred_json_path, "w", encoding="utf-8") as f:
        json.dump(predictions, f, ensure_ascii=False, indent=2)

    pairs = [(p["ground_truth"], p["predicted"]) for p in predictions]
    metrics = compute_metrics_from_pairs(pairs, class_codes)
    
    git_info = get_git_info()
    correct_count = sum(1 for p in predictions if p["ground_truth"] == p["predicted"])
    metrics["wilson_95_ci"] = wilson_ci(correct_count, len(predictions))
    metrics["boundary_tolerant_accuracy"] = round(sum(1 for p in predictions if p["ground_truth"] == p["predicted"] or p.get("is_boundary_match")) / max(1, len(predictions)), 4)
    
    dataset_sha = sha256_file(dataset_path) if os.path.exists(dataset_path) else "unknown"
    system_prompt_text = classifier._system_prompt() if hasattr(classifier, "_system_prompt") else ""
    
    metrics["metadata"] = {
        "git_commit": git_info.get("commit"),
        "git_branch": git_info.get("branch"),
        "dataset_split": dataset_split,
        "dataset_sha256": dataset_sha,
        "model": getattr(llm, "model", "unknown"),
        "temperature": getattr(llm, "temperature", 0.0),
        "num_ctx": getattr(llm, "num_ctx", 0),
        "max_input_chars": getattr(classifier, "max_input_chars", 0),
        "system_prompt_sha256": sha256_text(system_prompt_text),
        "seed": 42
    }

    subgroups = {}
    origin_types = ["scraped_official", "curated_anonymized"]
    for ot in origin_types:
        sub_preds = [p for p in predictions if p.get("origin_type") == ot]
        if sub_preds:
            sub_pairs = [(p["ground_truth"], p["predicted"]) for p in sub_preds]
            sub_m = compute_metrics_from_pairs(sub_pairs, class_codes)
            subgroups[f"origin_type_{ot}"] = {
                "accuracy": sub_m["accuracy"],
                "macro_f1": sub_m["macro_f1"],
                "count": len(sub_preds)
            }

    length_buckets = ["kisa", "orta", "uzun"]
    for lb in length_buckets:
        sub_preds = [p for p in predictions if p.get("length_bucket") == lb]
        if sub_preds:
            sub_pairs = [(p["ground_truth"], p["predicted"]) for p in sub_preds]
            sub_m = compute_metrics_from_pairs(sub_pairs, class_codes)
            subgroups[f"length_bucket_{lb}"] = {
                "accuracy": sub_m["accuracy"],
                "macro_f1": sub_m["macro_f1"],
                "count": len(sub_preds)
            }
    metrics["subgroups"] = subgroups

    latencies = [p["latency_ms"] for p in predictions]
    if latencies:
        metrics["latency"] = {
            "mean_ms": round(float(np.mean(latencies)), 2),
            "median_ms": round(float(np.median(latencies)), 2),
            "p95_ms": round(float(np.percentile(latencies, 95)), 2),
            "total_seconds": round(sum(latencies) / 1000.0, 2)
        }
    else:
        metrics["latency"] = {"mean_ms": 0.0, "median_ms": 0.0, "p95_ms": 0.0, "total_seconds": 0.0}

    metrics["timestamp"] = datetime.now().isoformat()

    print("Bootstrap CI hesaplanıyor...")
    ci_results = bootstrap_ci(predictions, class_codes)
    metrics["bootstrap_ci"] = ci_results

    metrics_path = os.path.join(out_dir, "metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print("Confusion matrix kaydediliyor...")
    save_confusion_matrix(predictions, class_codes, out_dir)

    print("Hata analizi raporu oluşturuluyor...")
    save_error_analysis(predictions, metrics, out_dir)

    print("Deney başarıyla tamamlandı ve tüm çıktılar kaydedildi!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="18 sınıflı sınıflandırma deneyi (E1)")
    parser.add_argument("--split", type=str, default="test", help="Veri seti split adı (örn: test, val)")
    parser.add_argument("--fresh", action="store_true", help="Önceki tahminleri yoksay ve sıfırdan başla")
    parser.add_argument("--limit", type=int, default=0, help="İşlenecek maksimum örnek sayısı (0 = tümü)")
    
    args = parser.parse_args()
    asyncio.run(run_experiment(dataset_split=args.split, fresh=args.fresh, limit=args.limit))
