import time

from conftest import SAMPLE_PETITION


def test_health_and_meta(client):
    health = client.get("/api/health").json()
    assert health["status"] == "ok"
    assert health["rag_available"] is False

    meta = client.get("/api/meta").json()
    codes = {t["code"] for t in meta["document_types"]}
    assert {"dilekce", "kanun", "bilinmiyor"} <= codes
    assert any(u["label"] == "Hukuk Müşavirliği" for u in meta["units"])
    assert [s["key"] for s in meta["pipeline_steps"]][0] == "extract"


def test_analyze_text_full_pipeline(client, fake_llm):
    response = client.post("/api/analyze-text", json={"text": SAMPLE_PETITION})
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["status"] == "completed"
    assert data["analysis"]["classification"]["document_type"] == "dilekce"  # "Dilekçe" normalize edildi
    assert data["analysis"]["summary"].startswith("Vatandaş")
    assert len(data["analysis"]["entities"]) == 1  # Bozuk öğe atlandı
    assert data["analysis"]["legislation_matches"][0]["article"] == "7"
    # Muhakeme: dilekçe için ust_yazi uygun değil -> cevap_yazisi
    assert data["draft"]["draft_type"] == "cevap_yazisi"
    assert data["draft"]["attachments_note"] is None
    # Muhakeme: dilekçe varsayılan önceliği normal
    assert data["routing"]["priority"] == "normal"
    rules = {v["rule"] for v in data["validation"]}
    assert {"draft_type_consistency", "priority_rules", "pii_detection"} <= rules
    assert all(v["message"] for v in data["validation"])
    assert [t["step"] for t in data["step_timings"]][0] == "extract"
    assert len(data["step_timings"]) == 8
    assert data["history_id"]
    assert data["source_name"] == "T.C."
    assert set(fake_llm.calls) == {"classify", "analyze", "legislation", "summary", "draft", "routing"}


def test_text_validation_errors(client):
    response = client.post("/api/analyze-text", json={"text": "kısa"})
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_input"

    response = client.post("/api/analyze-text", json={})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_llm_down_returns_503(client, fake_llm):
    fake_llm.fail_all = True
    response = client.post("/api/analyze-text", json={"text": SAMPLE_PETITION})
    assert response.status_code == 503
    assert response.json()["code"] == "llm_unavailable"


def test_partial_failure_is_reported(client, fake_llm):
    original = fake_llm.chat

    async def flaky(system_prompt, user_prompt, *, temperature=None):
        if "mevzuat uzmanı" in system_prompt:
            raise RuntimeError("mevzuat servisi çöktü")
        return await original(system_prompt, user_prompt)

    client.app.state.container.llm.chat = flaky
    data = client.post("/api/analyze-text", json={"text": SAMPLE_PETITION}).json()
    assert data["status"] == "partial"
    assert data["analysis"]["legislation_matches"] == []
    assert any(w.startswith("Mevzuat Eşleştirme") for w in data["warnings"])
    failed = [t for t in data["step_timings"] if t["status"] == "failed"]
    assert [t["step"] for t in failed] == ["legislation"]


def test_file_upload_and_rejections(client):
    files = {"file": ("../../evil dilekce.txt", SAMPLE_PETITION.encode("utf-8"), "text/plain")}
    data = client.post("/api/analyze", files=files).json()
    assert data["source_name"] == "evil dilekce.txt"  # Yol bileşenleri atıldı
    assert data["input_kind"] == "file"

    response = client.post("/api/analyze", files={"file": ("virus.exe", b"MZ", "application/octet-stream")})
    assert response.status_code == 415

    response = client.post("/api/analyze", files={"file": ("bos.txt", b"", "text/plain")})
    assert response.status_code == 400


def test_history_review_and_traversal(client):
    history_id = client.post("/api/analyze-text", json={"text": SAMPLE_PETITION, "title": "Kaldırım"}).json()["history_id"]

    page = client.get("/api/history", params={"q": "kaldırım"}).json()
    assert page["total"] == 1 and page["items"][0]["source_name"] == "Kaldırım"

    review = client.patch(f"/api/history/{history_id}/review",
                          json={"draft_status": "rejected", "reject_reason": "Eksik"}).json()
    assert review["draft_status"] == "rejected" and review["updated_at"]
    assert client.get("/api/history/stats").json()["by_draft_status"] == {"rejected": 1}

    assert client.get("/api/history/..%2F..%2Fsecret").status_code == 404
    assert client.patch("/api/history/yok/review", json={"draft_status": "approved"}).status_code == 404

    export = client.get(f"/api/export/{history_id}")
    assert "attachment" in export.headers["content-disposition"]
    assert export.json()["review"]["draft_status"] == "rejected"

    assert client.delete(f"/api/history/{history_id}").status_code == 200
    assert client.get(f"/api/history/{history_id}").status_code == 404


def test_job_progress(client):
    job_id = client.post("/api/jobs/text", json={"text": SAMPLE_PETITION}).json()["job_id"]
    deadline = time.time() + 10
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("completed", "failed"):
            break
        time.sleep(0.05)
    assert job["status"] == "completed", job
    assert all(step["status"] == "completed" for step in job["steps"])
    assert job["result"]["history_id"]
    assert client.get("/api/jobs/bilinmeyen").status_code == 404


def test_compare_clamps_score(client):
    data = client.post("/api/compare", json={"text1": SAMPLE_PETITION, "text2": SAMPLE_PETITION}).json()
    assert data["similarity_score"] == 1.0
    assert data["common_themes"] == ["talep"]


def test_security_headers(client):
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


def test_request_id_header(client):
    """Her API yanıtında X-Request-ID başlığı olmalı."""
    resp = client.get("/api/health")
    assert "X-Request-ID" in resp.headers
    rid = resp.headers["X-Request-ID"]
    assert len(rid) == 12

    # Gönderilen ID geri dönmeli
    resp2 = client.get("/api/health", headers={"X-Request-ID": "custom-id-abc"})
    assert resp2.headers["X-Request-ID"] == "custom-id-abc"


def test_mask_pii_endpoint(client):
    """PII maskeleme endpoint'i kişisel verileri maskelemeli."""
    text = "TC: 10000000146, Tel: 0532 123 45 67, Mail: test@example.com"
    resp = client.post("/api/mask-pii", json={"text": text})
    assert resp.status_code == 200
    data = resp.json()
    assert data["pii_count"] >= 2
    assert "10000000146" not in data["masked_text"]
    assert "***" in data["masked_text"]


def test_audit_log_on_review(client, fake_llm):
    """Memur kararı verdiğinde audit log kaydı tutulmalı."""
    resp = client.post("/api/analyze-text", json={"text": "T.C. Dilekçe — kaldırım onarımı talebi " * 5})
    hid = resp.json()["history_id"]

    # Taslak onayla
    resp = client.patch(f"/api/history/{hid}/review", json={"draft_status": "approved"})
    assert resp.status_code == 200
    review = resp.json()
    assert len(review["audit_log"]) == 1
    assert review["audit_log"][0]["action"] == "draft_status"
    assert "timestamp" in review["audit_log"][0]

    # Yönlendirme onayla
    resp = client.patch(f"/api/history/{hid}/review", json={"routing_status": "approved"})
    review = resp.json()
    assert len(review["audit_log"]) == 2


def test_export_all_records(client, fake_llm):
    """Tum analiz kayitlarini JSON olarak indirme."""
    # Iki analiz olustur
    client.post("/api/analyze-text", json={"text": "T.C. Dilekçe — kaldırım onarımı talebi " * 5})
    client.post("/api/analyze-text", json={"text": "T.C. Kanun teklifi — vergi düzenlemesi " * 5})

    resp = client.get("/api/history/export-all")
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    data = resp.json()
    assert data["total"] >= 2
    assert len(data["records"]) >= 2
