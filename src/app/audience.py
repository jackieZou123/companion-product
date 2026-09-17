"""请求端身份。鉴权和满 18 岁由客户端做完，再带 X-User-Id。"""

CUSTOMER = "customer"
STAFF = "staff"
ALLOWED = frozenset({CUSTOMER, STAFF})


def parse_audience(raw: str | None) -> str:
    """缺省当客户。非法值由 HTTP 层转 400。"""
    value = (raw or CUSTOMER).strip().lower()
    if value not in ALLOWED:
        raise ValueError("invalid_audience")
    return value
