from datetime import datetime, timedelta, timezone

from tests.helpers import FakeModel, FrozenClock, api_client, start_conversation

from app.character import CharacterRepository
from app.nudge.policy import NudgePolicy

_IDLE = timedelta(hours=24)
_RATE = timedelta(hours=24)
_NOW = datetime(2026, 9, 16, 12, tzinfo=timezone.utc)


def test_idle_care_pool_exists_and_is_not_clingy():
    profile = CharacterRepository().get("mei_li_kou")
    replies = profile.nudge("idle_care").replies
    assert replies
    joined = "".join(replies)
    assert "想你" not in joined
    assert "皮肤" in joined or "屏障" in joined or "护理" in joined


def test_policy_skips_until_idle():
    policy = NudgePolicy()
    spoken = _NOW - timedelta(hours=23)
    decision = policy.evaluate(
        stage="ongoing",
        profile_count=1,
        last_spoken_at=spoken,
        pending_count=0,
        last_created_at=None,
        now=_NOW,
        idle=_IDLE,
        rate=_RATE,
        has_replies=True,
    )
    assert not decision.should_create
    assert decision.reason == "idle_wait"


def test_policy_creates_after_idle_with_profile():
    policy = NudgePolicy()
    spoken = _NOW - timedelta(hours=25)
    decision = policy.evaluate(
        stage="ongoing",
        profile_count=1,
        last_spoken_at=spoken,
        pending_count=0,
        last_created_at=None,
        now=_NOW,
        idle=_IDLE,
        rate=_RATE,
        has_replies=True,
    )
    assert decision.should_create


def _spoken(client, text: str = "我是干皮，晚上还刺") -> str:
    conversation_id = start_conversation(client).json()["conversation_id"]
    turned = client.post(
        f"/v1/conversations/{conversation_id}/turns",
        json={"text": text},
    )
    assert turned.status_code == 200
    return conversation_id


def test_nudge_empty_before_idle_then_appears():
    clock = FrozenClock()
    model = FakeModel("先停掉刺激的步骤。")
    with api_client(model, clock=clock) as client:
        _spoken(client)
        assert client.get("/v1/me/nudges").json() == []
        clock.advance(hours=23)
        assert client.get("/v1/me/nudges").json() == []
        clock.advance(hours=2)
        items = client.get("/v1/me/nudges").json()
        assert len(items) == 1
        assert items[0]["code"] == "idle_care"
        profile = CharacterRepository().get("mei_li_kou")
        expected = set(profile.nudge("idle_care").replies)
        assert items[0]["text"] in expected
        again = client.get("/v1/me/nudges").json()
        assert again[0]["id"] == items[0]["id"]


def test_nudge_rate_limit_after_ack():
    clock = FrozenClock()
    model = FakeModel("先停掉刺激的步骤。")
    with api_client(model, clock=clock) as client:
        _spoken(client)
        clock.advance(hours=25)
        first = client.get("/v1/me/nudges").json()[0]
        acked = client.post(f"/v1/me/nudges/{first['id']}/ack")
        assert acked.status_code == 200
        assert client.get("/v1/me/nudges").json() == []
        clock.advance(hours=23)
        assert client.get("/v1/me/nudges").json() == []
        clock.advance(hours=2)
        second = client.get("/v1/me/nudges").json()
        assert len(second) == 1
        assert second[0]["id"] != first["id"]


def test_nudge_ttl_hides_expired_and_rate_blocks_new():
    clock = FrozenClock()
    model = FakeModel("先停掉刺激的步骤。")
    with api_client(
        model, clock=clock, nudge_ttl_hours=1, nudge_rate_hours=100
    ) as client:
        _spoken(client)
        clock.advance(hours=25)
        assert len(client.get("/v1/me/nudges").json()) == 1
        clock.advance(hours=2)
        assert client.get("/v1/me/nudges").json() == []


def test_nudge_requires_profile():
    clock = FrozenClock()
    model = FakeModel("先停掉刺激的步骤。")
    with api_client(model, clock=clock) as client:
        _spoken(client, "脸干得发紧，晚上还刺")
        clock.advance(hours=25)
        assert client.get("/v1/me/nudges").json() == []


def test_nudge_is_isolated_by_user():
    clock = FrozenClock()
    model = FakeModel("先停掉刺激的步骤。")
    with api_client(model, clock=clock, user_id="u_1") as client:
        _spoken(client)
        clock.advance(hours=25)
        mine = client.get("/v1/me/nudges").json()
        assert len(mine) == 1
        client.headers["X-User-Id"] = "u_2"
        assert client.get("/v1/me/nudges").json() == []
        foreign = client.post(f"/v1/me/nudges/{mine[0]['id']}/ack")
        assert foreign.status_code == 404


def test_dismiss_export_and_delete_me():
    clock = FrozenClock()
    model = FakeModel("先停掉刺激的步骤。")
    with api_client(model, clock=clock) as client:
        _spoken(client)
        clock.advance(hours=25)
        items = client.get("/v1/me/nudges").json()
        assert len(items) == 1
        export = client.get("/v1/me/export").json()
        assert len(export["nudges"]) == 1
        dismissed = client.post(f"/v1/me/nudges/{items[0]['id']}/dismiss")
        assert dismissed.status_code == 200
        assert client.get("/v1/me/nudges").json() == []
        client.delete("/v1/me")
        assert client.get("/v1/me/nudges").json() == []
