"""Export the local API contract without provisioning users or sample records."""

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from stokguard.core.config import Settings
from stokguard.main import create_app


def main():
    target = Path(sys.argv[1])
    with TemporaryDirectory(prefix="stokguard-openapi-") as temporary:
        app = create_app(Settings(data_dir=Path(temporary)))
        try:
            schema = app.openapi()
            target.write_text(
                json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        finally:
            app.state.engine.dispose()


if __name__ == "__main__":
    main()
