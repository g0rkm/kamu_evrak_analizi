import json
import os
import sys
import asyncio
import random
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.llm_service import LLMService
from app.agents.classifier_agent import ClassifierAgent

GROUND_TRUTH_MAP = {
    "cumhurbaskanligi_kararnamesi": "kararname",
}

SKIP_TYPES = {"diger", "mevzuat_gov_tr"}

SAMPLES_PER_TYPE = {
    "karar": 10,
    "yonetmelik": 10,
    "teblig": 10,
    "kanun": 10,
    "genelge": 6,
    "cumhurbaskanligi_kararnamesi": 5,
    "kararname": 3,
}


def load_and_sample(path):
    with open(path, "r", encoding="utf-8") as f:
        docs = json.load(f)

    by_type = defaultdict(list)
    for d in docs:
        t = d.get("type", d.get("source", "unknown"))
        if t not in SKIP_TYPES and "404 - Sayfa Bulunamadı" not in d.get("content", ""):
            by_type[t].append(d)

    samples = []
    for t, count in SAMPLES_PER_TYPE.items():
        pool = by_type.get(t, [])
        n = min(count, len(pool))
        if n > 0:
            chosen = random.sample(pool, n)
            for doc in chosen:
                gt = GROUND_TRUTH_MAP.get(t, t)
                samples.append((doc, gt))

    random.shuffle(samples)
    return samples


def compute_metrics(results):
    all_labels = set()
    for gt, pred in results:
        all_labels.add(gt)
        all_labels.add(pred)

    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)

    for gt, pred in results:
        if gt == pred:
            tp[gt] += 1
        else:
            fp[pred] += 1
            fn[gt] += 1

    total_correct = sum(1 for gt, pred in results if gt == pred)
    accuracy = total_correct / len(results) if results else 0

    print(f"\n{'='*60}")
    print(f"SONUCLAR ({len(results)} belge)")
    print(f"{'='*60}")
    print(f"Accuracy: {accuracy:.3f} ({total_correct}/{len(results)})")
    print(f"\n{'Tur':<20} {'P':>6} {'R':>6} {'F1':>6} {'TP':>4} {'FP':>4} {'FN':>4}")
    print("-" * 60)

    f1_scores = []
    gt_labels = set(gt for gt, _ in results)

    for label in sorted(gt_labels):
        p = tp[label] / (tp[label] + fp[label]) if (tp[label] + fp[label]) > 0 else 0
        r = tp[label] / (tp[label] + fn[label]) if (tp[label] + fn[label]) > 0 else 0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
        f1_scores.append(f1)
        print(f"{label:<20} {p:>6.3f} {r:>6.3f} {f1:>6.3f} {tp[label]:>4} {fp[label]:>4} {fn[label]:>4}")

    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0

    micro_tp = sum(tp.values())
    micro_fp = sum(fp.values())
    micro_fn = sum(fn.values())
    micro_p = micro_tp / (micro_tp + micro_fp) if (micro_tp + micro_fp) > 0 else 0
    micro_r = micro_tp / (micro_tp + micro_fn) if (micro_tp + micro_fn) > 0 else 0
    micro_f1 = 2 * micro_p * micro_r / (micro_p + micro_r) if (micro_p + micro_r) > 0 else 0

    print("-" * 60)
    print(f"{'Macro F1':<20} {'':>6} {'':>6} {macro_f1:>6.3f}")
    print(f"{'Micro F1':<20} {micro_p:>6.3f} {micro_r:>6.3f} {micro_f1:>6.3f}")

    errors = [(gt, pred) for gt, pred in results if gt != pred]
    if errors:
        print(f"\nHatali siniflandirmalar ({len(errors)}):")
        for gt, pred in errors:
            print(f"  GT: {gt:<20} -> Pred: {pred}")

    return {"accuracy": accuracy, "macro_f1": macro_f1, "micro_f1": micro_f1}


async def main():
    random.seed(42)
    data_path = "app/data/scraped/documents.json"
    samples = load_and_sample(data_path)
    print(f"[*] {len(samples)} belge secildi")

    gt_dist = defaultdict(int)
    for _, gt in samples:
        gt_dist[gt] += 1
    for t, c in sorted(gt_dist.items()):
        print(f"  {t}: {c}")

    llm = LLMService()
    classifier = ClassifierAgent(llm_service=llm)

    results = []
    for i, (doc, gt_label) in enumerate(samples):
        title = doc.get("title", "")[:60]
        content = f"{doc.get('title', '')}\n\n{doc.get('content', '')}".strip()
        print(f"[{i+1}/{len(samples)}] {title}...")

        for attempt in range(5):
            try:
                classification = await classifier.execute(content)
                pred = classification.document_type
                match = "OK" if pred == gt_label else "YANLIS"
                print(f"  GT={gt_label}, Pred={pred} [{match}]")
                results.append((gt_label, pred))
                break
            except Exception as e:
                if "429" in str(e) and attempt < 4:
                    wait = 2 ** (attempt + 2)
                    print(f"  Rate limit, {wait}s bekleniyor...")
                    await asyncio.sleep(wait)
                else:
                    print(f"  HATA: {e}")
                    break

        if not llm.is_local:
            await asyncio.sleep(3)

    await llm.close()
    compute_metrics(results)


if __name__ == "__main__":
    os.environ["PYTHONUTF8"] = "1"
    asyncio.run(main())
