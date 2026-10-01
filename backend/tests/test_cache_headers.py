"""Backend cache header regression (preview sandbox).

Verifies that GET /api/* reads carry Cache-Control: no-store (set by the
`api_reads_are_never_cached` middleware) while /api/files/<existing> keeps
its own `immutable` header (and 404s fall back to no-store).
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("EXPO_BACKEND_URL", "https://hallo-magic-test.preview.emergentagent.com").rstrip("/")
ORDER_ID = "6ab911a41640440ce55631b1"


def _cache(headers):
    return (headers.get("Cache-Control") or headers.get("cache-control") or "").lower()


class TestCacheHeaders:
    # method names contain "requires" so the autouse manager-token fixture (conftest.py) is skipped
    def test_menu_requires_no_store(self):
        r = requests.get(f"{BASE_URL}/api/menu", timeout=15)
        assert r.status_code == 200
        assert "no-store" in _cache(r.headers), _cache(r.headers)

    def test_order_detail_requires_no_store(self):
        r = requests.get(f"{BASE_URL}/api/orders/{ORDER_ID}", timeout=15)
        assert r.status_code == 200
        assert "no-store" in _cache(r.headers), _cache(r.headers)
        body = r.json()
        assert body.get("id") == ORDER_ID

    def test_orders_by_ids_requires_no_store(self):
        r = requests.get(f"{BASE_URL}/api/orders", params={"ids": ORDER_ID}, timeout=15)
        assert r.status_code == 200
        assert "no-store" in _cache(r.headers), _cache(r.headers)
        assert isinstance(r.json(), list)

    def test_files_missing_requires_no_store(self):
        r = requests.get(f"{BASE_URL}/api/files/does-not-exist-xyz", timeout=15)
        assert r.status_code == 404
        assert "no-store" in _cache(r.headers), _cache(r.headers)

    def test_files_existing_requires_immutable(self):
        """The preview edge proxy rewrites cache headers; the backend itself must still return `immutable` for existing files."""
        # Query the backend directly (bypassing the edge) when running inside the sandbox.
        local = "http://localhost:8001"
        from pymongo import MongoClient
        c = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = c[os.environ.get("DB_NAME", "test_database")]
        prod = db.products.find_one({"image_url": {"$regex": "^/api/files/"}})
        if not prod:
            pytest.skip("No product with /api/files/ image_url")
        url = f"{local}{prod['image_url']}"
        r = requests.get(url, timeout=10)
        assert r.status_code == 200
        cc = _cache(r.headers)
        assert "immutable" in cc, cc
