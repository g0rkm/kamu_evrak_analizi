import os
import sys
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

from app.services.pii_detector import PIIDetector

def main():
    os.makedirs("results/e5", exist_ok=True)
    
    test_set_path = "data/eval/pii/pii_test_set.json"
    if not os.path.exists(test_set_path):
        records = []
    else:
        with open(test_set_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            records = data.get("records", [])

    det = PIIDetector()

    total_tp = 0
    total_fp = 0
    total_fn = 0

    per_type_counts = {}
    false_positives = []
    false_negatives = []
    leaks = []
    total_records = len(records)

    for rec in records:
        rec_id = rec.get("id")
        text = rec.get("text", "")
        expected_list = rec.get("expected", [])

        findings = det.detect(text)
        
        detected_set = set()
        for f in findings:
            matched_text = text[f.start:f.end].strip()
            detected_set.add((f.type, matched_text))

        expected_set = set()
        for exp in expected_list:
            e_type = exp.get("type")
            e_val = exp.get("value", "").strip()
            if e_type and e_val:
                expected_set.add((e_type, e_val))

        all_types = {t for t, _ in detected_set} | {t for t, _ in expected_set}
        for t in all_types:
            if t not in per_type_counts:
                per_type_counts[t] = {"tp": 0, "fp": 0, "fn": 0}

        tp_items = detected_set & expected_set
        fp_items = detected_set - expected_set
        fn_items = expected_set - detected_set

        for t, val in tp_items:
            total_tp += 1
            per_type_counts[t]["tp"] += 1

        for t, val in fp_items:
            total_fp += 1
            per_type_counts[t]["fp"] += 1
            false_positives.append({"record_id": rec_id, "type": t, "matched_text": val})

        for t, val in fn_items:
            total_fn += 1
            per_type_counts[t]["fn"] += 1
            false_negatives.append({"record_id": rec_id, "type": t, "value": val})

        if expected_list:
            masked = det.mask_text(text)
            for exp in expected_list:
                e_val = exp.get("value", "").strip()
                if e_val and e_val in masked:
                    leaks.append({"record_id": rec_id, "value": e_val})

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    per_type_results = {}
    f1_sum = 0.0
    active_types_count = 0

    for t, counts in per_type_counts.items():
        tp = counts["tp"]
        fp = counts["fp"]
        fn = counts["fn"]
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * p * r / (p + r)) if (p + r) > 0 else 0.0
        per_type_results[t] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1, 4)
        }
        f1_sum += f1
        active_types_count += 1

    macro_f1 = (f1_sum / active_types_count) if active_types_count > 0 else 0.0

    output_data = {
        "overall": {
            "TP": total_tp,
            "FP": total_fp,
            "FN": total_fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "micro_f1": round(micro_f1, 4),
            "macro_f1": round(macro_f1, 4),
            "total_records": total_records
        },
        "per_type": per_type_results,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "mask_leakage": {
            "leak_count": len(leaks),
            "leaks": leaks
        }
    }

    with open("results/e5/pii_eval.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print("PII Evaluation Complete.")
    print(f"Total Records: {total_records}")
    print(f"Precision: {precision:.4f} | Recall: {recall:.4f} | Micro-F1: {micro_f1:.4f} | Macro-F1: {macro_f1:.4f}")
    print(f"False Positives: {total_fp} | False Negatives: {total_fn}")
    print(f"Mask Leakage Count: {len(leaks)}")

if __name__ == "__main__":
    main()
