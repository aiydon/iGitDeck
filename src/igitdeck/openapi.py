"""Export the API contract for frontend type generation."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from igitdeck.config import Settings
from igitdeck.main import create_app


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="igiddeck-openapi-") as temp:
        root = Path(temp)
        settings = Settings(
            data_dir=root / "data",
            frontend_dist=root / "frontend",
            auto_sync=False,
            fetch_metadata=False,
            log_level="ERROR",
        )
        app = create_app(settings, with_logging=False)
        print(json.dumps(app.openapi(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
