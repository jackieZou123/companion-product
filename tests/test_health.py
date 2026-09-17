from tests.helpers import api_client


def test_root_serves_companion_ui():
    with api_client() as client:
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "玫莉蔻" in response.text


def test_companion_assets_are_served():
    with api_client() as client:
        js = client.get("/assets/index.js")
        css = client.get("/assets/index.css")
        assert js.status_code == 200
        assert css.status_code == 200
        assert "我已满 18 岁" not in js.text
        assert "打开玫莉蔻" in js.text
        assert "确认预约" in js.text
        assert "新对话" not in js.text
        assert "我是女性" not in js.text
        assert "选择性别" not in js.text
        assert "玫莉蔻" in js.text
        assert "--leaf" in css.text
        assert ".fab" in css.text


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


def test_readyz_not_ready_is_503():
    with api_client(openai_api_key="") as client:
        response = client.get("/readyz")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"


def test_metrics_start_empty():
    with api_client() as client:
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.json()["turns"]["count"] == 0
