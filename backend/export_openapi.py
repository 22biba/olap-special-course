"""
Export OpenAPI spec so Swagger docs can be viewed without running the server.
Run from backend: python export_openapi.py
Then open openapi.json in https://editor.swagger.io or use npx @redocly/cli preview openapi.json
"""
import json
from pathlib import Path

from main import app

_OUT = Path(__file__).resolve().parent.parent / "docs" / "openapi.json"
_OUT.parent.mkdir(parents=True, exist_ok=True)
_OUT.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
print(f"Exported: {_OUT}")
