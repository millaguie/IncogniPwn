import pytest

from fastapi.testclient import TestClient
from app.main import app
from app.services.hash_lookup import lookup_range, validate_prefix
from app.services.metrics import update_dataset_metrics


client = TestClient(app)


@pytest.fixture
def sample_data(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.DATA_DIR", str(tmp_path))
    data = (
        "0018A45C4D1DEF81644B54AB7F969B88D65:1\n"
        "00D4F6E8FA6EECAD2A3AA415EEC418D38EC:2\n"
        "011053FD0102E94D6AE2F8B83D76FAF94F6:1\n"
    )
    (tmp_path / "21BD1.txt").write_text(data)
    return tmp_path


class TestValidatePrefix:
    def test_valid_lowercase(self):
        assert validate_prefix("21bd1") is True

    def test_valid_uppercase(self):
        assert validate_prefix("21BD1") is True

    def test_valid_all_hex(self):
        assert validate_prefix("00000") is True
        assert validate_prefix("FFFFF") is True
        assert validate_prefix("abcde") is True

    def test_too_short(self):
        assert validate_prefix("21BD") is False

    def test_too_long(self):
        assert validate_prefix("21BD12") is False

    def test_invalid_chars(self):
        assert validate_prefix("21BG1") is False

    def test_empty(self):
        assert validate_prefix("") is False


class TestLookupRange:
    def test_found(self, sample_data):
        results, found, _ = lookup_range("21BD1")
        assert found is True
        assert len(results) == 3
        assert "0018A45C4D1DEF81644B54AB7F969B88D65:1" in results

    def test_not_found(self, sample_data):
        results, found, _ = lookup_range("ZZZZZ")
        assert found is False

    def test_file_not_exists(self, sample_data):
        results, found, _ = lookup_range("AAAAA")
        assert found is False

    def test_case_insensitive(self, sample_data):
        results_upper, _, _ = lookup_range("21BD1")
        results_lower, _, _ = lookup_range("21bd1")
        assert results_upper == results_lower

    def test_malformed_lines_counted(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.config.DATA_DIR", str(tmp_path))
        data = "A123456789ABCDEF0123456789ABCD12345:1\nBADLINE\n"
        (tmp_path / "AAAAA.txt").write_text(data)
        results, found, ignored = lookup_range("AAAAA")
        assert found is True
        assert len(results) == 1
        assert ignored == 1


class TestPadding:
    def test_no_padding(self, sample_data):
        results, _, _ = lookup_range("21BD1", with_padding=False)
        assert len(results) == 3

    def test_padding_adds_entries(self, sample_data):
        results, _, _ = lookup_range("21BD1", with_padding=True)
        assert len(results) >= 800
        assert len(results) <= 1000

    def test_padding_entries_have_count_zero(self, sample_data):
        results, _, _ = lookup_range("21BD1", with_padding=True)
        padding_entries = [
            r for r in results if r.endswith(":0") and not r.startswith("00")
        ]
        assert len(padding_entries) > 0

    def test_padding_preserves_real_data(self, sample_data):
        results, _, _ = lookup_range("21BD1", with_padding=True)
        assert "0018A45C4D1DEF81644B54AB7F969B88D65:1" in results


class TestAPIEndpoints:
    def test_range_success(self, sample_data):
        response = client.get("/range/21BD1")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        assert "0018A45C4D1DEF81644B54AB7F969B88D65:1" in response.text

    def test_range_not_found(self, sample_data):
        response = client.get("/range/AAAAA")
        assert response.status_code == 404

    def test_range_invalid_prefix(self, sample_data):
        response = client.get("/range/ZZZZZ")
        assert response.status_code == 400

    def test_range_case_insensitive(self, sample_data):
        r1 = client.get("/range/21BD1")
        r2 = client.get("/range/21bd1")
        assert r1.text == r2.text

    def test_health(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_ready_with_data(self, sample_data):
        response = client.get("/ready")
        assert response.status_code == 200

    def test_ready_without_data(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.config.DATA_DIR", str(tmp_path))
        response = client.get("/ready")
        assert response.status_code == 503

    def test_padding_header(self, sample_data):
        response = client.get("/range/21BD1", headers={"Add-Padding": "true"})
        assert response.status_code == 200
        lines = response.text.strip().split("\n")
        assert len(lines) >= 800

    def test_no_padding_by_default(self, sample_data):
        response = client.get("/range/21BD1")
        lines = response.text.strip().split("\n")
        assert len(lines) == 3

    def test_metrics_endpoint(self):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert b"incognipwn" in response.content


class TestDatasetMetrics:
    def test_update_from_status_file(self, tmp_path, monkeypatch):
        import json
        import time

        monkeypatch.setattr("app.config.DATA_DIR", str(tmp_path))
        ts = int(time.time()) - 3600
        status = {
            "timestamp": ts,
            "success": 1,
            "duration_seconds": 900,
            "file_count": 1048576,
            "expected_files": 1048576,
        }
        (tmp_path / ".update_status.json").write_text(json.dumps(status))

        update_dataset_metrics()

        response = client.get("/metrics")
        assert response.status_code == 200
        body = response.text
        assert (
            "incognipwn_active_hash_files 1.048576e+06" in body
            or "incognipwn_active_hash_files 1048576" in body
        )
        assert "incognipwn_last_update_success 1" in body
        assert "incognipwn_last_update_duration_seconds 900" in body
        assert "incognipwn_hash_files_expected_total" in body
        assert "incognipwn_last_update_timestamp_seconds" in body
        assert "incognipwn_dataset_age_seconds" in body

    def test_update_fallback_without_status_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.config.DATA_DIR", str(tmp_path))
        for prefix in ["A0000", "A0001", "A0002"]:
            (tmp_path / f"{prefix}.txt").write_text("AABB:1\n")

        update_dataset_metrics()

        response = client.get("/metrics")
        assert response.status_code == 200
        assert "incognipwn_active_hash_files 3" in response.text
