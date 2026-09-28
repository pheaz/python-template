from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec"
SCHEMA = SPEC / "schema"


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_schema(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")

    return cast(dict[str, Any], value)


def _validate(path: Path, schema_path: Path) -> None:
    instance = _load_yaml(path)
    schema = _load_schema(schema_path)

    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(instance),
        key=lambda error: list(error.absolute_path),
    )

    if errors:
        details = "\n".join(
            f"{path}: {'/'.join(str(part) for part in error.absolute_path)}: "
            f"{error.message}"
            for error in errors
        )
        raise ValueError(details)


def main() -> None:
    _validate(
        SPEC / "requirements" / "core.yaml",
        SCHEMA / "requirement.schema.json",
    )
    _validate(
        SPEC / "capabilities" / "core.yaml",
        SCHEMA / "capability.schema.json",
    )

    flow_schema = SCHEMA / "flow.schema.json"

    for flow_path in sorted((SPEC / "flows").glob("*.yaml")):
        _validate(flow_path, flow_schema)

    print("Specification is valid.")


if __name__ == "__main__":
    main()
