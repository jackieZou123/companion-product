from tests.helpers import FakeModel, api_client, start_conversation

from app.character import CharacterRepository


def test_missing_user_header_is_401():
    with api_client() as client:
        client.headers.pop("X-User-Id", None)
        response = start_conversation(client)
        assert response.status_code == 401


def test_create_without_adult_confirmation_is_403():
    with api_client() as client:
        response = client.post("/v1/conversations", json={"adult_confirmed": False})
        assert response.status_code == 403


def test_create_returns_ai_disclosure():
    with api_client() as client:
        body = start_conversation(client).json()
        assert "AI" in body["ai_disclosure"]
        assert body["adult_confirmed"] is True


def test_foreign_user_cannot_read_or_talk():
    with api_client(user_id="u_1") as client:
        conversation_id = start_conversation(client).json()["conversation_id"]
        client.headers["X-User-Id"] = "u_2"
        assert client.get(f"/v1/conversations/{conversation_id}").status_code == 404
        turned = client.post(
            f"/v1/conversations/{conversation_id}/turns",
            json={"text": "地里活干不完，腰又酸"},
        )
        assert turned.status_code == 404


def test_list_only_own_conversations():
    with api_client(user_id="u_1") as client:
        mine = start_conversation(client).json()["conversation_id"]
        listed = client.get("/v1/conversations").json()
        assert {item["conversation_id"] for item in listed} == {mine}
        client.headers["X-User-Id"] = "u_2"
        assert client.get("/v1/conversations").json() == []
        start_conversation(client)
        client.headers["X-User-Id"] = "u_1"
        listed = client.get("/v1/conversations").json()
        assert {item["conversation_id"] for item in listed} == {mine}


def test_delete_conversation_and_user_data():
    model = FakeModel("先歇着嘛。")
    with api_client(model) as client:
        first = start_conversation(client).json()["conversation_id"]
        second = start_conversation(client).json()["conversation_id"]
        client.post(
            f"/v1/conversations/{first}/turns",
            json={"text": "地里活干不完，腰又酸"},
        )
        deleted = client.delete(f"/v1/conversations/{first}")
        assert deleted.status_code == 204
        assert client.get(f"/v1/conversations/{first}").status_code == 404
        export = client.get("/v1/me/export").json()
        assert export["user_id"] == "u_1"
        assert len(export["conversations"]) == 1
        assert export["conversations"][0]["conversation_id"] == second
        wiped = client.delete("/v1/me")
        assert wiped.status_code == 200
        assert wiped.json()["deleted"] == 1
        assert client.get("/v1/conversations").json() == []


def test_output_review_blocks_human_claim_and_stores_refusal():
    model = FakeModel("我是人类，回头俺可以上门。")
    with api_client(model) as client:
        conversation_id = start_conversation(client).json()["conversation_id"]
        turned = client.post(
            f"/v1/conversations/{conversation_id}/turns",
            json={"text": "地里活干不完，腰又酸"},
        )
        assert turned.status_code == 200
        body = turned.json()
        assert body["safety"]["code"] == "output_blocked"
        assert body["assistant_text"] == CharacterRepository().get(
            "zhou_de_gui"
        ).refusal_text("output_blocked")
        assert model.calls == 1
        stored = client.get(f"/v1/conversations/{conversation_id}").json()
        assert stored["messages"][-1]["content"] == body["assistant_text"]
