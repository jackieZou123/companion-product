"""陪伴对话页。源码在仓库 web/，构建产物在 src/app/web。"""

from pathlib import Path

from fastapi.responses import FileResponse

WEB_DIR = Path(__file__).resolve().parents[1] / "web"


def companion_page() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html", media_type="text/html; charset=utf-8")
