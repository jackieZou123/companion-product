"""呼唤池占位。不点名时去掉 {address}，避免把花名写进回复。"""


def fill_address(text: str, address: str = "") -> str:
    if address:
        return text.replace("{address}", address)
    return (
        text.replace("，{address}，", "，")
        .replace("，{address}", "")
        .replace("{address}，", "")
        .replace("{address}", "")
    )
