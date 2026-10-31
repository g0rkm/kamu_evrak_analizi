import csv
import json
import os
import re
import time
from collections import defaultdict
import datetime

from app.core.taxonomy import DOCUMENT_TYPES, normalize_code
from experiments.e1_classification import compute_metrics_from_pairs, wilson_ci, bootstrap_ci, get_git_info


def classify_taxonomy_keywords(title: str, content: str) -> tuple[str, float, str]:
    """Baseline A1: Taxonomy Keyword Matcher
    Uses DOCUMENT_TYPES and matches title and content keywords deterministically.
    """
    t_low = (title or "").lower()
    c_low = (content or "")[:3000].lower()
    
    best_code = "resmi_yazi"
    max_score = 0.0
    
    for doc_type in DOCUMENT_TYPES:
        score = 0.0
        label_lower = getattr(doc_type, "label", "").lower()
        if label_lower and label_lower in t_low:
            score += 3.0
            
        keywords = getattr(doc_type, "keywords", []) or []
        for kw in keywords:
            kw_low = kw.lower()
            if not kw_low:
                continue
            if kw_low in t_low:
                score += 2.0
            if kw_low in c_low:
                count = c_low.count(kw_low)
                if count > 3:
                    count = 3
                score += 1.0 * count
                
        if score > max_score:
            max_score = score
            best_code = doc_type.code
            
    return best_code, float(max_score), "taxonomy_keywords"


def classify_structural_rules(title: str, content: str) -> tuple[str, float, str]:
    """Baseline A2: Structural & Header Rule Classifier
    Inspects title and body using ordered surface/header heuristics.
    """
    t_low = (title or "").lower()
    body = (content or "")[:3000]
    body_low = body.lower()
    
    # 1. Kanun
    if re.search(r"kanun numaras[ıi]|kabul tarihi", body, re.I) or (re.search(r"\bkanun\b", t_low, re.I) and "kararname" not in t_low and "tarife" not in t_low):
        return "kanun", 1.0, "structural_rules"
    # 2. Kararname
    if "cumhurbaşkanlığı kararnamesi" in t_low or "kanun hükmünde kararname" in t_low or "karar numarası" in body_low or "cbk" in t_low:
        return "kararname", 1.0, "structural_rules"
    # 3. Karar
    if "cumhurbaşkanı kararı" in body_low or "karar sayısı" in t_low or "mahkemesi kararı" in body_low or re.search(r"\bkarar[ıi]?\b", t_low, re.I):
        return "karar", 1.0, "structural_rules"
    # 4. Yönetmelik
    if "yönetmelik" in t_low or "yönetmeliği" in t_low:
        return "yonetmelik", 1.0, "structural_rules"
    # 5. Tebliğ
    if "tebliğ" in t_low or "tarifesi" in t_low:
        return "teblig", 1.0, "structural_rules"
    # 6. Genelge
    if "genelge" in t_low or re.search(r"\bGENELGE\b", body):
        return "genelge", 1.0, "structural_rules"
    # 7. Yönerge
    if "yönerge" in t_low or "yönergesi" in t_low:
        return "yonerge", 1.0, "structural_rules"
    # 8. İlan
    if "ilan" in t_low or "ilân" in t_low or "ihale" in body_low:
        return "ilan", 1.0, "structural_rules"
    # 9. Sözleşme
    if "sözleşme" in t_low or "protokol" in t_low or "mutabakat" in t_low:
        return "sozlesme", 1.0, "structural_rules"
    # 10. Tutanak
    if "tutanak" in t_low or "tutanağı" in t_low or "imza altına alınmıştır" in body_low:
        return "tutanak", 1.0, "structural_rules"
    # 11. Rapor
    if "rapor" in t_low or "bulgular" in body_low:
        return "rapor", 1.0, "structural_rules"
    # 12. Şikayet
    if "şikayet" in t_low or "şikâyet" in t_low or "mağduriyet" in body_low:
        return "sikayet", 1.0, "structural_rules"
    # 13. Dilekçe
    if "dilekçe" in t_low or "başvuru" in t_low:
        return "dilekce", 1.0, "structural_rules"
    # 14. Görüş sorma
    if "görüş" in t_low or "mütalaa" in body_low:
        return "gorus_sorma", 1.0, "structural_rules"
    # 15. Talep yazısı
    if "talep" in t_low or "tahsis" in body_low or "ödenek" in body_low:
        return "talep_yazisi", 1.0, "structural_rules"
    # 16. Bilgilendirme
    if "bilgilendirme" in t_low or "duyuru" in t_low or "bilgilerinize sunulur" in body_low:
        return "bilgilendirme", 1.0, "structural_rules"
    # 17. Kurum içi
    if "iç yazışma" in t_low or "kurum içi" in t_low or "personelimizin" in body_low:
        return "kurum_ici", 1.0, "structural_rules"
    
    # 18. Default fallback
    return "resmi_yazi", 1.0, "structural_rules"


def run_rule_baselines(split: str = "test") -> dict:
    """Runs Baseline A1 and A2 on the specified split, computes metrics,
    and saves metrics and predictions JSON files.
    """
    data_path = os.path.join("data", "eval", "classification", f"{split}.json")
    if not os.path.exists(data_path):
        print(f"Dataset not found at {data_path}")
        return {}
    
    with open(data_path, "r", encoding="utf-8") as f:
        records = json.load(f)
        
    class_codes = DOCUMENT_TYPES.codes()
        
    pairs_a1 = []
    pairs_a2 = []
    preds_a1 = []
    preds_a2 = []
    
    start_time = time.time()
    
    for rec in records:
        title = rec.get("title", "") or ""
        content = rec.get("content", "") or ""
        doc_id = rec.get("doc_id") or rec.get("id")
        true_label = normalize_code(rec.get("ground_truth") or rec.get("document_type") or "resmi_yazi")
        sec_cands = rec.get("secondary_candidates", [])
        
        # A1: Taxonomy Keywords
        t0 = time.time()
        pred_a1, score_a1, _ = classify_taxonomy_keywords(title, content)
        latency_a1 = (time.time() - t0) * 1000
        
        normalized_pred_a1 = normalize_code(pred_a1)
        pairs_a1.append((true_label, normalized_pred_a1))
        preds_a1.append({
            "doc_id": doc_id,
            "ground_truth": true_label,
            "predicted": normalized_pred_a1,
            "confidence": score_a1,
            "secondary_candidates": sec_cands,
            "is_boundary_match": (normalized_pred_a1 in sec_cands),
            "latency_ms": round(latency_a1, 4)
        })
        
        # A2: Structural Rules
        t0 = time.time()
        pred_a2, score_a2, _ = classify_structural_rules(title, content)
        latency_a2 = (time.time() - t0) * 1000
        
        normalized_pred_a2 = normalize_code(pred_a2)
        pairs_a2.append((true_label, normalized_pred_a2))
        preds_a2.append({
            "doc_id": doc_id,
            "ground_truth": true_label,
            "predicted": normalized_pred_a2,
            "confidence": score_a2,
            "secondary_candidates": sec_cands,
            "is_boundary_match": (normalized_pred_a2 in sec_cands),
            "latency_ms": round(latency_a2, 4)
        })
        
    total_time = (time.time() - start_time) * 1000
    total_samples = len(records) if records else 1
    
    metrics_a1 = compute_metrics_from_pairs(pairs_a1, class_codes)
    metrics_a2 = compute_metrics_from_pairs(pairs_a2, class_codes)
    
    correct_a1 = sum(1 for t, p in pairs_a1 if t == p)
    acc_a1 = correct_a1 / total_samples
    wilson_a1 = wilson_ci(correct_a1, total_samples)
    boot_a1 = bootstrap_ci(preds_a1, class_codes, n_boot=2000, seed=42)
    
    correct_a2 = sum(1 for t, p in pairs_a2 if t == p)
    acc_a2 = correct_a2 / total_samples
    wilson_a2 = wilson_ci(correct_a2, total_samples)
    boot_a2 = bootstrap_ci(preds_a2, class_codes, n_boot=2000, seed=42)
    
    if isinstance(metrics_a1, dict):
        metrics_a1.setdefault("accuracy", acc_a1)
        metrics_a1.setdefault("wilson_95_ci", wilson_a1)
        metrics_a1.setdefault("bootstrap_ci", boot_a1)
        metrics_a1.setdefault("latency", total_time / total_samples)
        metrics_a1["boundary_tolerant_accuracy"] = round(sum(1 for p in preds_a1 if p["ground_truth"] == p["predicted"] or p["is_boundary_match"]) / total_samples, 4)
        metrics_a1["mean_latency_ms"] = round(sum(p["latency_ms"] for p in preds_a1) / total_samples, 4)
        
    if isinstance(metrics_a2, dict):
        metrics_a2.setdefault("accuracy", acc_a2)
        metrics_a2.setdefault("wilson_95_ci", wilson_a2)
        metrics_a2.setdefault("bootstrap_ci", boot_a2)
        metrics_a2.setdefault("latency", total_time / total_samples)
        metrics_a2["boundary_tolerant_accuracy"] = round(sum(1 for p in preds_a2 if p["ground_truth"] == p["predicted"] or p["is_boundary_match"]) / total_samples, 4)
        metrics_a2["mean_latency_ms"] = round(sum(p["latency_ms"] for p in preds_a2) / total_samples, 4)

    git_info = get_git_info()
    
    results = {
        "timestamp": datetime.datetime.now().isoformat(),
        "split": split,
        "git_info": git_info,
        "baseline_a1_taxonomy_keywords": metrics_a1,
        "baseline_a2_structural_rules": metrics_a2
    }
    
    predictions_output = {
        "timestamp": datetime.datetime.now().isoformat(),
        "split": split,
        "predictions_a1": preds_a1,
        "predictions_a2": preds_a2
    }
    
    os.makedirs(os.path.join("results", "e2"), exist_ok=True)
    
    with open(os.path.join("results", "e2", "baseline_rule_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    with open(os.path.join("results", "e2", "baseline_rule_predictions.json"), "w", encoding="utf-8") as f:
        json.dump(predictions_output, f, ensure_ascii=False, indent=2)
        
    print("--- Baseline A1 (Taxonomy Keywords) Metrics ---")
    print(json.dumps(metrics_a1, ensure_ascii=False, indent=2))
    print("\n--- Baseline A2 (Structural Rules) Metrics ---")
    print(json.dumps(metrics_a2, ensure_ascii=False, indent=2))
    
    return results


if __name__ == "__main__":
    run_rule_baselines("test")
