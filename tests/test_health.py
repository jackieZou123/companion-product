from tests.helpers import api_client


def test_root_redirects_to_docs():
    with api_client() as client:
        response = client.get("/", follow_redirects=False)
        assert response.status_code in {302, 307}
        assert response.headers["location"].endswith("/docs")


def test_healthz():
    with api_client() as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_readyz_reports_provider():
    with api_client() as client:
        response = client.get("/readyz")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["model"] == "gpt-5.4-mini"


def test_metrics_start_empty():
    with api_client() as client:
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.json()["turns"]["count"] == 0
