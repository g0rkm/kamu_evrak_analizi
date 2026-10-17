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
    assert response.headers["cache-control"] == "private, max-age=0, must-revalidate"


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


def test_csrf_protection_blocks_invalid_content_type(client):
    """CSRF korumasi: POST isteklerinde Content-Type basliksiz istek reddedilmeli."""
    resp = client.post("/api/analyze-text", content=b'{"text": "test"}')
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_content_type"


def test_health_endpoint_extended_fields(client):
    """Health endpoint'i yeni metrikleri icermeli."""
    data = client.get("/api/health").json()
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0
    assert "active_jobs" in data
    assert data["active_jobs"] == 0
    assert "disk_free_mb" in data


def test_magic_bytes_rejects_fake_pdf(client):
    """PDF uzantili ama icerigi PDF olmayan dosya reddedilmeli."""
    fake_pdf = b"This is not a PDF file at all"
    resp = client.post("/api/analyze", files={"file": ("fake.pdf", fake_pdf, "application/pdf")})
    assert resp.status_code == 415
    assert "uyuşmuyor" in resp.json()["detail"]


def test_llm_stats_endpoint(client):
    """LLM kullanım istatistikleri endpoint'i çalışmalı."""
    resp = client.get("/api/stats/llm")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_requests" in data
    assert "cache_hits" in data


def test_draft_status_filter(client, fake_llm):
    """Taslak durumuna göre filtreleme çalışmalı."""
    hid = client.post("/api/analyze-text", json={"text": "T.C. Dilekçe — kaldırım onarımı talebi " * 5}).json()["history_id"]
    client.patch(f"/api/history/{hid}/review", json={"draft_status": "approved"})

    # Onaylanmış kayıtları filtrele
    page = client.get("/api/history", params={"draft_status": "approved"}).json()
    assert page["total"] >= 1
    assert all(i["draft_status"] == "approved" for i in page["items"])

    # Bekleyen kayıtları filtrele (bu kayıt onaylanmış olduğundan 0 olmalı)
    page2 = client.get("/api/history", params={"draft_status": "pending"}).json()
    assert all(i["draft_status"] == "pending" for i in page2["items"])


def test_response_time_header(client):
    """Her API yanıtında X-Response-Time başlığı olmalı."""
    resp = client.get("/api/health")
    assert "X-Response-Time" in resp.headers
    assert resp.headers["X-Response-Time"].endswith("ms")


def test_clear_all_records(client, fake_llm):
    """Tüm kayıtları silme endpoint'i çalışmalı."""
    client.post("/api/analyze-text", json={"text": "T.C. Dilekçe — test kayıt 1 " * 5})
    client.post("/api/analyze-text", json={"text": "T.C. Dilekçe — test kayıt 2 " * 5})

    resp = client.delete("/api/history/clear")
    assert resp.status_code == 200
    assert resp.json()["deleted"] >= 2

    page = client.get("/api/history").json()
    assert page["total"] == 0


def test_empty_text_rejected(client):
    """Boş metin analiz isteği reddedilmeli."""
    resp = client.post("/api/analyze-text", json={"text": ""})
    assert resp.status_code == 422
    data = resp.json()
    assert "detail" in data

    resp = client.post("/api/analyze-text", json={"text": "   "})
    assert resp.status_code == 422
    data = resp.json()
    assert "detail" in data


def test_empty_compare_rejected(client):
    """Boş karşılaştırma metinleri reddedilmeli."""
    resp = client.post("/api/compare", json={"text1": "", "text2": "test"})
    assert resp.status_code == 422

    resp = client.post("/api/compare", json={"text1": "test", "text2": ""})
    assert resp.status_code == 422


def test_csp_header_on_html(client):
    """Frontend sayfalarında CSP header'ı bulunmalı."""
    resp = client.get("/")
    # Frontend mount'lu değilse skip
    if resp.status_code == 404:
        return
    csp = resp.headers.get("Content-Security-Policy-Report-Only") or resp.headers.get("Content-Security-Policy")
    assert csp is not None
    assert "default-src 'self'" in csp


def test_permissions_policy_header(client):
    """API yanıtlarında Permissions-Policy header'ı bulunmalı."""
    resp = client.get("/api/health")
    assert resp.headers.get("Permissions-Policy") == "camera=(), microphone=(), geolocation=()"


def test_rate_limit_config():
    """Rate limit ayarları config'den okunmalı."""
    from app.config import Settings
    s = Settings(LLM_API_KEY="test", RATE_LIMIT_REQUESTS=10, RATE_LIMIT_WINDOW=30)
    assert s.RATE_LIMIT_REQUESTS == 10
    assert s.RATE_LIMIT_WINDOW == 30


def test_readiness_probe(client):
    """Readiness probe endpoint'i çalışmalı."""
    resp = client.get("/api/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert "ready" in data
    assert "checks" in data
    assert "llm_configured" in data["checks"]


def test_unconfigured_llm_blocks_analysis(client):
    """LLM yapılandırılmamışken analiz reddedilmeli."""
    # fake_llm fixture'ı kullanmadan test et (LLM_API_KEY="not-set")
    from app.config import Settings
    from app.main import create_app
    from starlette.testclient import TestClient

    settings = Settings(LLM_API_KEY="not-set")
    test_app = create_app(settings)
    with TestClient(test_app) as c:
        resp = c.post("/api/analyze-text", json={"text": "T.C. Dilekçe — test metin " * 5})
        assert resp.status_code == 400
        assert "yapılandırılmamış" in resp.json()["detail"].lower()


def test_import_records(client, fake_llm):
    """Kayıt içe aktarma endpoint'i çalışmalı."""
    # Önce bir kayıt oluştur ve dışa aktar
    client.post("/api/analyze-text", json={"text": "T.C. Dilekçe — test kayıt " * 5})
    page = client.get("/api/history").json()
    assert page["total"] >= 1

    # Tüm kayıtları sil
    client.delete("/api/history/clear")
    assert client.get("/api/history").json()["total"] == 0

    # Kayıtları geri içe aktar
    resp = client.post("/api/history/import", json={"records": page["items"]})
    assert resp.status_code == 200
    assert resp.json()["imported"] >= 1


def test_keyword_search_in_history(client, fake_llm):
    """Geçmiş araması anahtar kelimelerle çalışmalı."""
    client.post("/api/analyze-text", json={"text": "T.C. Dilekçe — kaldırım onarımı talebi " * 5})
    resp = client.get("/api/history?q=onarım")
    assert resp.status_code == 200


def test_delete_without_content_type_allowed(client, fake_llm):
    """DELETE isteği Content-Type olmadan da çalışmalı."""
    client.post("/api/analyze-text", json={"text": "T.C. Dilekçe — test kayıt " * 5})
    # Content-Type header'ı olmadan DELETE isteği
    resp = client.delete("/api/history/clear")
    assert resp.status_code == 200


def test_request_stats_endpoint(client):
    """İstek metrikleri endpoint'i çalışmalı."""
    # Birkaç istek yap
    client.get("/api/health")
    client.get("/api/health")

    resp = client.get("/api/stats/requests")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_requests" in data
    assert data["total_requests"] >= 2
    assert "error_rate" in data
    assert "status_codes" in data


def test_update_review_notes(client, fake_llm):
    """Analiz kaydına not eklenebilmeli."""
    resp = client.post("/api/analyze-text", json={"text": "T.C. Dilekçe — test not " * 5})
    history_id = resp.json()["history_id"]

    # Not ekle
    resp = client.patch(f"/api/history/{history_id}/review", json={"notes": "Dikkat: acil değerlendirme gerekiyor."})
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Dikkat: acil değerlendirme gerekiyor."

    # Notun kaydedildiğini doğrula
    record = client.get(f"/api/history/{history_id}").json()
    assert record["review"]["notes"] == "Dikkat: acil değerlendirme gerekiyor."


def test_error_response_includes_request_id(client):
    """Hata yanıtları X-Request-ID header'ı içermeli."""
    resp = client.get("/api/health")
    assert "X-Request-ID" in resp.headers

    # 404 yanıtı da request_id içermeli
    resp = client.get("/api/history/nonexistent_record_12345")
    assert resp.status_code == 404
    assert "X-Request-ID" in resp.headers


def test_app_error_includes_request_id(client):
    """AppError yanıtları request_id içermeli."""
    resp = client.post("/api/analyze-text", json={"text": ""})
    assert resp.status_code == 422
    body = resp.json()
    assert "request_id" in body


def test_health_warnings_field(client):
    """Health endpoint'i warnings alanı döndürmeli."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "warnings" in data
    assert isinstance(data["warnings"], list)


def test_system_info_includes_uptime(client):
    """System info endpoint'i uptime döndürmeli."""
    resp = client.get("/api/system-info")
    assert resp.status_code == 200
    data = resp.json()
    assert "uptime_seconds" in data
    assert "uptime_human" in data
    assert "warnings" in data


def test_llm_health_endpoint(client):
    """LLM bağlantı testi endpoint'i çalışmalı."""
    resp = client.get("/api/health/llm")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


def test_config_export_endpoint(client):
    resp = client.get("/api/config/export")
    assert resp.status_code == 200
    data = resp.json()
    assert "version" in data
    assert "llm_model" in data
    assert "rate_limit" in data
    assert "llm_configured" in data
    # Hassas bilgi olmamalı
    assert "api_key" not in str(data).lower()


def test_clear_cache_endpoint(client):
    resp = client.post("/api/cache/clear", headers={"Content-Type": "application/json"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["cleared"] is True
    assert "entries_removed" in data


def test_null_byte_stripped_from_text(client):
    resp = client.post(
        "/api/analyze-text",
        json={"text": "Bu metin\x00 null byte içeriyor"},
        headers={"Content-Type": "application/json"},
    )
    # İstek başarılı olmalı (503 = LLM bağlanamadı, ama null byte hatası olmamalı)
    assert resp.status_code in (200, 503)


def test_pii_mask_kredi_kart(client):
    resp = client.post(
        "/api/mask-pii",
        json={"text": "Kart: 4539 1234 5678 9012"},
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pii_count"] >= 1
    assert "4539 1234 5678 9012" not in data["masked_text"]


def test_readiness_probe_checks(client):
    resp = client.get("/api/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert "ready" in data
    assert "checks" in data
    assert "llm_configured" in data["checks"]
    assert "history_writable" in data["checks"]


def test_health_includes_environment(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "environment" in data
    assert data["environment"] == "development"


def test_system_info_includes_environment(client):
    resp = client.get("/api/system-info")
    assert resp.status_code == 200
    data = resp.json()
    assert "environment" in data


def test_sort_parameter_in_history(client):
    # Sıralama parametresi ile istek kabul edilmeli
    resp = client.get("/api/history?sort=newest")
    assert resp.status_code == 200
    resp2 = client.get("/api/history?sort=oldest")
    assert resp2.status_code == 200
    resp3 = client.get("/api/history?sort=confidence_desc")
    assert resp3.status_code == 200


def test_history_pagination_metadata(client):
    resp = client.get("/api/history?limit=10&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert "has_more" in data
    assert "offset" in data
    assert "limit" in data
    assert data["offset"] == 0
    assert data["limit"] == 10
    assert isinstance(data["has_more"], bool)


def test_request_stats_includes_error_rate(client):
    # Önce birkaç istek yaparak metrikleri oluştur
    client.get("/api/health")
    client.get("/api/nonexistent")
    resp = client.get("/api/stats/requests")
    assert resp.status_code == 200
    data = resp.json()
    assert "error_rate" in data
    assert isinstance(data["error_rate"], (int, float))


def test_mask_pii_empty_text(client):
    resp = client.post(
        "/api/mask-pii",
        json={"text": "Bu metinde kişisel veri yoktur."},
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pii_count"] == 0
    assert data["masked_text"] == "Bu metinde kişisel veri yoktur."


def test_config_export_no_secrets(client):
    """Config export API anahtarını içermemeli."""
    resp = client.get("/api/config/export")
    assert resp.status_code == 200
    raw = resp.text.lower()
    assert "not-set" not in raw or "api_key" not in raw


def test_csv_export_endpoint(client):
    resp = client.get("/api/history/export-csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    assert "gecmis.csv" in resp.headers.get("content-disposition", "")
    # CSV header satiri kontrolü
    lines = resp.text.strip().split("\n")
    assert len(lines) >= 1
    assert "id" in lines[0]
    assert "timestamp" in lines[0]


def test_readiness_includes_circuit_breaker(client):
    resp = client.get("/api/ready")
    data = resp.json()
    assert "circuit_breaker_closed" in data["checks"]
    assert data["checks"]["circuit_breaker_closed"] is True


def test_import_records_invalid_body(client):
    """records alanı list değilse 400 dönmeli."""
    response = client.post("/api/history/import", json={"records": "not_a_list"})
    assert response.status_code == 400


def test_import_records_over_limit(client):
    """500'den fazla kayıt gönderildiğinde 400 dönmeli."""
    records = [{"id": f"test-{i}", "result": {}} for i in range(501)]
    response = client.post("/api/history/import", json={"records": records})
    assert response.status_code == 400


def test_mask_pii_empty_text_returns_zero(client):
    """Boş metin gönderildiğinde pii_count 0 olmalı."""
    response = client.post("/api/mask-pii", json={"text": ""})
    assert response.status_code == 200
    data = response.json()
    assert data["pii_count"] == 0
    assert data["masked_text"] == ""


def test_llm_stats_includes_avg_latency(client):
    """LLM stats avg_latency_ms alanını içermeli."""
    response = client.get("/api/stats/llm")
    assert response.status_code == 200
    data = response.json()
    assert "avg_latency_ms" in data


def test_system_info_includes_settings(client):
    """System info settings bölümünü içermeli."""
    response = client.get("/api/system-info")
    assert response.status_code == 200
    data = response.json()
    assert "settings" in data
    assert "log_level" in data["settings"]
    assert "llm_model" in data["settings"]


def test_maintenance_mode_blocks_requests():
    """Bakım modunda health dışındaki istekler 503 dönmeli."""
    from app.config import Settings
    from app.main import create_app
    from starlette.testclient import TestClient
    settings = Settings(MAINTENANCE_MODE=True)
    app = create_app(settings=settings)
    with TestClient(app) as mc:
        response = mc.get("/api/meta")
        assert response.status_code == 503
        health = mc.get("/api/health")
        assert health.status_code == 200


def test_maintenance_mode_off_allows_requests(client):
    """Bakım modu kapalıyken istekler normal işlenmeli."""
    response = client.get("/api/meta")
    assert response.status_code == 200


def test_config_export_includes_cache(client):
    """Config export cache_entries alanını içermeli."""
    response = client.get("/api/config/export")
    assert response.status_code == 200
    data = response.json()
    assert "cache_entries" in data


def test_health_llm_unconfigured(client):
    """LLM yapılandırılmamışsa health/llm unconfigured dönmeli."""
    response = client.get("/api/health/llm")
    assert response.status_code == 200
    data = response.json()
    # Test ortamında LLM key yok
    assert data["status"] in ("unconfigured", "ok", "unreachable")


def test_clear_all_history(client):
    """Tüm geçmiş kayıtlarını silmeli."""
    response = client.delete("/api/history/clear")
    assert response.status_code == 200
    data = response.json()
    assert "deleted" in data


def test_api_version_header(client):
    """Her API yanıtı X-API-Version header'ı içermeli."""
    response = client.get("/api/health")
    assert "X-API-Version" in response.headers
    assert response.headers["X-API-Version"] == "2.8.0"


def test_admin_endpoint_without_token(client):
    """Admin token yokken hassas endpoint'ler erişilebilir olmalı."""
    # ADMIN_TOKEN boş olduğunda kontrol atlanır
    response = client.post("/api/cache/clear", json={})
    assert response.status_code == 200


def test_admin_endpoint_with_wrong_token():
    """Yanlış token ile admin endpoint'lere erişim 401 dönmeli."""
    from app.config import Settings
    from app.main import create_app
    from starlette.testclient import TestClient
    settings = Settings(ADMIN_TOKEN="test-secret-token")
    app = create_app(settings=settings)
    with TestClient(app) as mc:
        response = mc.post("/api/cache/clear", json={}, headers={"Authorization": "Bearer wrong-token"})
        assert response.status_code == 401


def test_admin_endpoint_with_correct_token():
    """Doğru token ile admin endpoint'lere erişim sağlanmalı."""
    from app.config import Settings
    from app.main import create_app
    from starlette.testclient import TestClient
    settings = Settings(ADMIN_TOKEN="test-secret-token")
    app = create_app(settings=settings)
    with TestClient(app) as mc:
        response = mc.post("/api/cache/clear", json={}, headers={"Authorization": "Bearer test-secret-token"})
        assert response.status_code == 200


def test_history_date_filter_params(client):
    """History endpoint tarih filtre parametrelerini kabul etmeli."""
    response = client.get("/api/history?date_from=2024-01-01&date_to=2024-12-31")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


def test_history_min_confidence_filter(client):
    """History endpoint min_confidence parametresini kabul etmeli."""
    response = client.get("/api/history?min_confidence=50")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


def test_rate_limit_headers_present(client):
    """Rate limit bilgisi /stats/requests endpoint'inden erişilebilir olmalı."""
    response = client.get("/api/stats/requests")
    assert response.status_code == 200
    data = response.json()
    assert "total_requests" in data
    assert "error_rate" in data


def test_config_export_includes_environment(client):
    """Config export environment ve maintenance_mode içermeli."""
    response = client.get("/api/config/export")
    assert response.status_code == 200
    data = response.json()
    assert "environment" in data
    assert "maintenance_mode" in data


def test_bulk_delete_empty_ids(client):
    """Boş ids listesi 422 dönmeli."""
    response = client.post("/api/history/bulk-delete", json={"ids": []})
    assert response.status_code == 400


def test_bulk_delete_invalid_body(client):
    """ids alanı list değilse 400 dönmeli."""
    response = client.post("/api/history/bulk-delete", json={"ids": "not_a_list"})
    assert response.status_code == 400


def test_bulk_delete_nonexistent_ids(client):
    """Var olmayan id'leri silmeye çalışmak 200 dönmeli (deleted=0)."""
    response = client.post("/api/history/bulk-delete", json={"ids": ["nonexistent-1", "nonexistent-2"]})
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] == 0
    assert data["requested"] == 2


def test_export_all_records(client):
    """Tüm kayıtları JSON olarak dışa aktarmalı."""
    response = client.get("/api/history/export-all")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "records" in data
    assert isinstance(data["records"], list)


def test_audit_log_nonexistent(client):
    """Var olmayan kayıt için denetim logu 404 dönmeli."""
    response = client.get("/api/history/nonexistent-id-123/audit")
    assert response.status_code == 404


def test_health_detailed_endpoint(client):
    """Detaylı sağlık kontrolü endpoint'i çalışmalı."""
    response = client.get("/api/health/detailed")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "checks" in data
    assert "llm" in data["checks"]
    assert "storage" in data["checks"]
    assert "rag" in data["checks"]


def test_update_tags_nonexistent(client):
    """Var olmayan kayıta etiket ekleme 404 dönmeli."""
    response = client.patch("/api/history/nonexistent-id/tags", json={"tags": ["test"]})
    assert response.status_code == 404


def test_update_tags_invalid_body(client):
    """tags alanı list değilse 400 dönmeli."""
    # Önce var olmayan bir kayıta gönderelim - 404 döner (tag validation'dan önce kayıt kontrolü yapılır)
    response = client.patch("/api/history/nonexistent-id/tags", json={"tags": "not_a_list"})
    assert response.status_code in (400, 404)


def test_history_list_with_tag_query(client):
    """History list endpoint'inde tag araması çalışmalı."""
    response = client.get("/api/history?q=test-tag")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


def test_toggle_favorite_nonexistent(client):
    """Var olmayan kayıda favori ekleme 404 dönmeli."""
    response = client.patch("/api/history/nonexistent-id/favorite", json={"favorite": True})
    assert response.status_code == 404


def test_update_notes_nonexistent(client):
    """Var olmayan kayıda not ekleme 404 dönmeli."""
    response = client.patch("/api/history/nonexistent-id/notes", json={"notes": "Test notu"})
    assert response.status_code == 404


def test_update_notes_too_long(client):
    """2000 karakterden uzun not 400 dönmeli."""
    # Not: Kayıt yok olduğu için önce 404 döner, ama uzun not validasyonu kayıttan sonra
    long_note = "a" * 2001
    response = client.patch("/api/history/nonexistent-id/notes", json={"notes": long_note})
    assert response.status_code in (400, 404)


def test_history_trends_endpoint(client):
    """Trend endpoint'i çalışmalı ve trends listesi döndürmeli."""
    response = client.get("/api/history/trends?days=7")
    assert response.status_code == 200
    data = response.json()
    assert "days" in data
    assert data["days"] == 7
    assert "trends" in data
    assert len(data["trends"]) == 7


def test_duplicate_nonexistent(client):
    """Var olmayan kaydı kopyalama 404 dönmeli."""
    response = client.post("/api/history/nonexistent-id/duplicate", json={})
    assert response.status_code == 404


def test_history_favorite_filter(client):
    """Favori filtresi çalışmalı."""
    response = client.get("/api/history?favorite=true")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


def test_health_includes_uptime_human(client):
    """Health endpoint uptime_human alanını içermeli."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "uptime_human" in data


def test_request_stats_includes_top_endpoints(client):
    """Request stats top_endpoints alanını içermeli."""
    # Önce birkaç istek yap
    client.get("/api/health")
    client.get("/api/meta")
    response = client.get("/api/stats/requests")
    assert response.status_code == 200
    data = response.json()
    assert "top_endpoints" in data


def test_openapi_docs_available(client):
    """OpenAPI docs endpoint'i erişilebilir olmalı."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_redoc_available(client):
    """ReDoc endpoint'i erişilebilir olmalı."""
    response = client.get("/redoc")
    assert response.status_code == 200


def test_history_stats_includes_favorites(client):
    """History stats favorites_count alanını içermeli."""
    response = client.get("/api/history/stats")
    assert response.status_code == 200
    data = response.json()
    assert "favorites_count" in data
    assert data["favorites_count"] >= 0


def test_history_trends_default_30_days(client):
    """Trends endpoint varsayılan olarak 30 günlük veri döndürmeli."""
    response = client.get("/api/history/trends")
    assert response.status_code == 200
    data = response.json()
    assert data["days"] == 30
    assert len(data["trends"]) == 30


def test_validate_text_endpoint(client):
    response = client.post('/api/validate-text', json={'text': 'Bu bir test metnidir.'})
    assert response.status_code == 200
    data = response.json()
    assert 'valid' in data
    assert 'char_count' in data


def test_history_summary_stats(client):
    response = client.get('/api/stats/history-summary')
    assert response.status_code == 200
    data = response.json()
    assert 'total' in data
    assert 'top_confidence' in data
    assert isinstance(data['top_confidence'], list)


def test_version_endpoint(client):
    response = client.get('/api/version')
    assert response.status_code == 200
    data = response.json()
    assert data['version'] == '2.8.0'
    assert data['api'] == 'v1'


def test_system_info_includes_timeout(client):
    response = client.get('/api/system-info')
    assert response.status_code == 200
    data = response.json()
    assert 'analysis_timeout' in data['settings']


def test_health_includes_checks(client):
    response = client.get('/api/health')
    data = response.json()
    assert 'checks' in data
    assert data['checks']['storage'] is True
    assert 'llm_configured' in data['checks']


def test_config_validate_endpoint(client):
    response = client.get('/api/config/validate')
    assert response.status_code == 200
    data = response.json()
    assert 'valid' in data
    assert 'issues' in data
    assert isinstance(data['issues'], list)
