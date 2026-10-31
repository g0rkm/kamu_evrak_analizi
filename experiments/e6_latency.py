import os
import sys
import json
import time
import random
import statistics
import subprocess
import asyncio

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

from app.services.llm_service import LLMService
from app.agents.classifier_agent import ClassifierAgent
from app.agents.analyzer_agent import AnalyzerAgent
from app.config import get_settings

MODEL = "gemma4:12b"
REPS = 5
DOCS_PER_BUCKET = 3
SEED = 42
CONC_SWEEP_DOCS = 6


def nvidia_smi_used_mib() -> int | None:
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=True
        )
        return int(res.stdout.strip().splitlines()[0])
    except Exception:
        return None


def gpu_name() -> str | None:
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip().splitlines()[0]
    except Exception:
        return None


def ollama_version() -> str | None:
    try:
        res = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except Exception:
        return None


def summarize(values: list[float]) -> dict:
    if not values:
        return {
            "n": 0,
            "mean": 0.0,
            "std": 0.0,
            "median": 0.0,
            "p95": 0.0,
            "min": 0.0,
            "max": 0.0,
            "ci95": [0.0, 0.0]
        }
    
    n = len(values)
    mean_val = statistics.mean(values)
    std_val = statistics.pstdev(values) if n > 1 else 0.0
    median_val = statistics.median(values)
    
    sorted_vals = sorted(values)
    p95_idx = min(n - 1, int(round(0.95 * (n - 1))))
    p95_val = sorted_vals[p95_idx]
    min_val = sorted_vals[0]
    max_val = sorted_vals[-1]
    
    # Bootstrap 95% CI for mean
    rng = random.Random(SEED)
    bootstrap_means = []
    for _ in range(2000):
        sample = [rng.choice(values) for _ in range(n)]
        bootstrap_means.append(statistics.mean(sample))
    bootstrap_means.sort()
    ci_lo = bootstrap_means[int(0.025 * len(bootstrap_means))]
    ci_hi = bootstrap_means[int(0.975 * len(bootstrap_means))]
    
    return {
        "n": n,
        "mean": mean_val,
        "std": std_val,
        "median": median_val,
        "p95": p95_val,
        "min": min_val,
        "max": max_val,
        "ci95": [ci_lo, ci_hi]
    }


async def timed(coro):
    t0 = time.perf_counter()
    res = await coro
    return time.perf_counter() - t0, res


async def main():
    os.makedirs("results/e6", exist_ok=True)
    
    settings = get_settings()
    llm = LLMService()
    clf = ClassifierAgent(llm_service=llm)
    anl = AnalyzerAgent(llm_service=llm)
    
    baseline_vram = nvidia_smi_used_mib()
    peak_vram = baseline_vram or 0
    
    def update_peak():
        nonlocal peak_vram
        current = nvidia_smi_used_mib()
        if current is not None and current > peak_vram:
            peak_vram = current

    # Veri yükleme
    docs_path = os.path.join("app", "data", "scraped", "documents.json")
    all_docs = []
    if os.path.exists(docs_path):
        with open(docs_path, "r", encoding="utf-8") as f:
            try:
                all_docs = json.load(f)
            except Exception:
                all_docs = []
    
    # Uygun belgeleri filtreleme
    filtered_docs = []
    for d in all_docs:
        content = d.get("content", "")
        if len(content) >= 200:
            filtered_docs.append({
                "id": d.get("id", str(random.randint(1000, 9999))),
                "content": content,
                "char_count": len(content)
            })
            
    # Eğer dosya boşsa ya da yeterli veri yoksa simüle edilmiş veri listesi oluştur
    if not filtered_docs:
        for i in range(10):
            dummy_text = "Bu test belgesi içeriktir. " * random.randint(10, 400)
            filtered_docs.append({
                "id": f"dummy_{i+1}",
                "content": dummy_text,
                "char_count": len(dummy_text)
            })

    buckets = {"kisa": [], "orta": [], "uzun": []}
    for d in filtered_docs:
        cc = d["char_count"]
        if cc < 1500:
            buckets["kisa"].append(d)
        elif cc <= 6000:
            buckets["orta"].append(d)
        else:
            buckets["uzun"].append(d)
            
    rng = random.Random(SEED)
    sampled_doc_ids = {}
    selected_buckets = {}
    
    for b_name, b_list in buckets.items():
        chosen = rng.sample(b_list, min(len(b_list), DOCS_PER_BUCKET)) if b_list else []
        selected_buckets[b_name] = chosen
        sampled_doc_ids[b_name] = [doc["id"] for doc in chosen]

    failures = 0
    
    # 1. Isınma
    print("Model ısıtılıyor...")
    if selected_buckets["kisa"]:
        try:
            await clf.execute(selected_buckets["kisa"][0]["content"])
        except Exception:
            pass
    update_peak()
    
    # 2. Soğuk Başlangıç
    cold_start_s = None
    try:
        subprocess.run(["ollama", "stop", MODEL], capture_output=True, text=True)
        time.sleep(2)
        if selected_buckets["orta"]:
            target_doc = selected_buckets["orta"][0]["content"]
        elif selected_buckets["kisa"]:
            target_doc = selected_buckets["kisa"][0]["content"]
        else:
            target_doc = "Soğuk başlangıç test içeriğidir."
            
        c_time, _ = await timed(clf.execute(target_doc))
        cold_start_s = c_time
    except Exception:
        cold_start_s = None
    update_peak()
    
    # Yeniden ısınma
    if selected_buckets["kisa"]:
        try:
            await clf.execute(selected_buckets["kisa"][0]["content"])
        except Exception:
            pass

    # 3. Koşul A — İzole Sınıflandırıcı
    isolated_classifier_raw = {b: [] for b in buckets}
    for b_name, docs in selected_buckets.items():
        for doc in docs:
            for _ in range(REPS):
                c_cache = getattr(llm, "_cache", None)
                if c_cache is not None:
                    c_cache.clear()
                try:
                    lat, _ = await timed(clf.execute(doc["content"]))
                    isolated_classifier_raw[b_name].append(lat)
                except Exception:
                    failures += 1
                update_peak()
                
    isolated_classifier_summary = {b: summarize(vals) for b, vals in isolated_classifier_raw.items()}

    # 4. Koşul B — Eşzamanlı Pipeline (Classifier ‖ Analyzer)
    conc_clf_raw = {b: [] for b in buckets}
    stage_wall_raw = {b: [] for b in buckets}
    
    for b_name, docs in selected_buckets.items():
        for doc in docs:
            for _ in range(REPS):
                c_cache = getattr(llm, "_cache", None)
                if c_cache is not None:
                    c_cache.clear()
                try:
                    res = await asyncio.gather(
                        timed(clf.execute(doc["content"])),
                        timed(anl.execute(doc["content"]))
                    )
                    clf_lat = res[0][0]
                    wall_t = max(res[0][0], res[1][0])
                    conc_clf_raw[b_name].append(clf_lat)
                    stage_wall_raw[b_name].append(wall_t)
                except Exception:
                    failures += 1
                update_peak()

    concurrent_pipeline_summary = {
        "classifier_latency": {b: summarize(vals) for b, vals in conc_clf_raw.items()},
        "stage_wall": {b: summarize(vals) for b, vals in stage_wall_raw.items()}
    }

    # 5. Eşzamanlılık Taraması
    sweep_pool = []
    for b_list in selected_buckets.values():
        sweep_pool.extend(b_list)
    if not sweep_pool:
        sweep_pool = filtered_docs
    sweep_docs = (sweep_pool * ((CONC_SWEEP_DOCS // len(sweep_pool)) + 1))[:CONC_SWEEP_DOCS]
    sweep_texts = [d["content"] for d in sweep_docs]
    
    # (a) Sıralı
    t_seq_start = time.perf_counter()
    for text in sweep_texts:
        c_cache = getattr(llm, "_cache", None)
        if c_cache is not None:
            c_cache.clear()
        try:
            await clf.execute(text)
        except Exception:
            failures += 1
        update_peak()
    seq_total = time.perf_counter() - t_seq_start
    seq_throughput = len(sweep_texts) / seq_total if seq_total > 0 else 0.0

    # (b) Eşzamanlı
    c_cache = getattr(llm, "_cache", None)
    if c_cache is not None:
        c_cache.clear()
    t_conc_start = time.perf_counter()
    try:
        await asyncio.gather(*[clf.execute(text) for text in sweep_texts])
    except Exception:
        failures += len(sweep_texts)
    conc_total = time.perf_counter() - t_conc_start
    conc_throughput = len(sweep_texts) / conc_total if conc_total > 0 else 0.0
    update_peak()

    concurrency_sweep_data = {
        "sequential": {
            "total_s": seq_total,
            "throughput_docs_s": seq_throughput,
            "n": len(sweep_texts)
        },
        "concurrent": {
            "total_s": conc_total,
            "throughput_docs_s": conc_throughput,
            "n": len(sweep_texts)
        }
    }

    provenance = {
        "model": MODEL,
        "ollama_version": ollama_version(),
        "gpu": gpu_name(),
        "baseline_vram_mib": baseline_vram,
        "peak_vram_mib": peak_vram,
        "reps": REPS,
        "docs_per_bucket": DOCS_PER_BUCKET,
        "seed": SEED,
        "llm_max_concurrent_requests": settings.LLM_MAX_CONCURRENT_REQUESTS,
        "num_ctx": settings.LLM_NUM_CTX,
        "temperature": settings.LLM_TEMPERATURE,
        "classifier_truncate_chars": clf.max_input_chars,
        "sampled_doc_ids": sampled_doc_ids,
        "timestamp": time.time()
    }

    final_output = {
        "provenance": provenance,
        "cold_start_s": cold_start_s,
        "isolated_classifier": isolated_classifier_summary,
        "concurrent_pipeline": concurrent_pipeline_summary,
        "concurrency_sweep": concurrency_sweep_data,
        "failures": failures
    }

    # JSON Kaydı
    json_path = os.path.join("results", "e6", "latency.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)

    # CSV Kaydı
    csv_path = os.path.join("results", "e6", "latency.csv")
    csv_lines = ["condition,bucket,n,mean_s,median_s,p95_s,std_s,ci_lo,ci_hi"]
    
    for b, stats in isolated_classifier_summary.items():
        csv_lines.append(f"isolated_classifier,{b},{stats['n']},{stats['mean']:.4f},{stats['median']:.4f},{stats['p95']:.4f},{stats['std']:.4f},{stats['ci95'][0]:.4f},{stats['ci95'][1]:.4f}")
        
    for b, stats in concurrent_pipeline_summary["classifier_latency"].items():
        csv_lines.append(f"concurrent_classifier,{b},{stats['n']},{stats['mean']:.4f},{stats['median']:.4f},{stats['p95']:.4f},{stats['std']:.4f},{stats['ci95'][0]:.4f},{stats['ci95'][1]:.4f}")
        
    for b, stats in concurrent_pipeline_summary["stage_wall"].items():
        csv_lines.append(f"concurrent_stage_wall,{b},{stats['n']},{stats['mean']:.4f},{stats['median']:.4f},{stats['p95']:.4f},{stats['std']:.4f},{stats['ci95'][0]:.4f},{stats['ci95'][1]:.4f}")
        
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("\n".join(csv_lines))

    # Konsol ASCII Özet
    print("\n================ E6 PERFORMANS ÖLÇÜM ÖZETİ ================")
    print(f"Model: {MODEL} | GPU: {gpu_name()}")
    print(f"Soğuk Başlangıç Süresi: {cold_start_s:.2f}s" if cold_start_s else "Soğuk Başlangıç: Ölçülemedi")
    print(f"Tepe VRAM Kullanımı: {peak_vram} MiB (Taban: {baseline_vram} MiB)")
    print(f"Hatalar / Başarısız İstekler: {failures}")
    print("----------------------------------------------------------")
    print("İzole Sınıflandırıcı Ortalamaları:")
    for b, st in isolated_classifier_summary.items():
        print(f"  - {b}: {st['mean']:.3f}s (n={st['n']}, p95={st['p95']:.3f}s)")
    print("----------------------------------------------------------")
    print(f"Throughput Taraması ({len(sweep_texts)} belge):")
    print(f"  - Sıralı Toplam: {seq_total:.2f}s | Hız: {seq_throughput:.2f} doc/s")
    print(f"  - Eşzamanlı Toplam: {conc_total:.2f}s | Hız: {conc_throughput:.2f} doc/s")
    print("==========================================================")

    await llm.close()

if __name__ == "__main__":
    asyncio.run(main())
