from app.audience import CUSTOMER, STAFF
from app.dialogue.intent import (
    BOOKING_STATUS,
    CARE_BOOKING,
    CARE_STATUS,
    NONE,
    IntentPolicy,
)


def test_book_sunday_care_extracts_slots():
    decision = IntentPolicy().evaluate("我想预约星期天的护理")
    assert decision.code == CARE_BOOKING
    assert decision.confirm_required is True
    assert decision.slots == {"service": "care", "date_hint": "sunday"}
    assert "不代替系统下单" in decision.hint


def test_booking_and_care_status():
    policy = IntentPolicy()
    assert policy.evaluate("我约到哪了").code == BOOKING_STATUS
    assert policy.evaluate("护理做到哪了").code == CARE_STATUS
    assert policy.evaluate("护理做到哪了").confirm_required is False


def test_skin_talk_and_staff_ops_are_none():
    policy = IntentPolicy()
    assert policy.evaluate("脸干得发紧，晚上还刺").code == NONE
    assert policy.evaluate("今晚谁值班").code == NONE
    assert policy.evaluate("产品使用状态").code == NONE


def test_staff_audience_suppresses_customer_booking():
    policy = IntentPolicy()
    assert policy.evaluate("我想预约星期天的护理", audience=STAFF).code == NONE
    assert policy.evaluate("我想预约星期天的护理", audience=CUSTOMER).code == CARE_BOOKING


def test_wake_plus_booking_still_hits():
    decision = IntentPolicy().evaluate("玫莉蔻我想预约星期天的护理")
    assert decision.code == CARE_BOOKING
    assert decision.slots is not None
    assert decision.slots["date_hint"] == "sunday"
