from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import yaml
from jsonschema import validate as validate_jsonschema

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec"
SCHEMA = SPEC / "schema"

type JsonScalar = bool | int | float | str | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type Record = tuple[Path, dict[str, JsonValue]]


def _normalize(value: object) -> JsonValue:
    if value is None:
        return None

    if isinstance(value, str | bool | int | float):
        return value

    if isinstance(value, list):
        values = cast("list[object]", value)

        return [_normalize(item) for item in values]

    if isinstance(value, dict):
        mapping = cast("dict[object, object]", value)
        result: dict[str, JsonValue] = {}

        for key, item in mapping.items():
            if not isinstance(key, str):
                raise TypeError("Specification object keys must be strings")

            result[key] = _normalize(item)

        return result

    raise TypeError(f"Unsupported specification value: {type(value).__name__}")


def _load_yaml(path: Path) -> JsonValue:
    return _normalize(
        cast(
            "object",
            yaml.safe_load(path.read_text(encoding="utf-8")),
        )
    )


def _load_json(path: Path) -> JsonValue:
    return _normalize(
        cast(
            "object",
            json.loads(path.read_text(encoding="utf-8")),
        )
    )


def _object(
    value: JsonValue,
    context: str,
) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise TypeError(f"{context} must contain an object")

    return value


def _array(
    value: JsonValue,
    context: str,
) -> list[JsonValue]:
    if not isinstance(value, list):
        raise TypeError(f"{context} must contain an array")

    return value


def _string(
    value: JsonValue,
    context: str,
) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{context} must be a string")

    return value


def _required_string(
    record: dict[str, JsonValue],
    key: str,
    context: str,
) -> str:
    return _string(
        record[key],
        f"{context}.{key}",
    )


def _optional_string(
    record: dict[str, JsonValue],
    key: str,
    context: str,
) -> str | None:
    value = record.get(key)

    if value is None:
        return None

    return _string(
        value,
        f"{context}.{key}",
    )


def _optional_string_list(
    record: dict[str, JsonValue],
    key: str,
    context: str,
) -> list[str]:
    value = record.get(key)

    if value is None:
        return []

    return [
        _string(
            item,
            f"{context}.{key}",
        )
        for item in _array(
            value,
            f"{context}.{key}",
        )
    ]


def _validate_file(
    path: Path,
    schema_path: Path,
) -> dict[str, JsonValue]:
    instance = _load_yaml(path)

    schema = _object(
        _load_json(schema_path),
        str(schema_path),
    )

    validate_jsonschema(
        instance=instance,
        schema=schema,
    )

    return _object(
        instance,
        str(path),
    )


def _load_registry(
    directory: Path,
    key: str,
    schema_path: Path,
) -> list[Record]:
    result: list[Record] = []

    for path in sorted(directory.glob("*.yaml")):
        document = _validate_file(
            path,
            schema_path,
        )

        values = _array(
            document[key],
            f"{path}:{key}",
        )

        result.extend(
            (
                path,
                _object(
                    value,
                    str(path),
                ),
            )
            for value in values
        )

    return result


def _load_flows() -> list[Record]:
    return [
        (
            path,
            _validate_file(
                path,
                SCHEMA / "flow.schema.json",
            ),
        )
        for path in sorted((SPEC / "flows").glob("*.yaml"))
    ]


def _index_records(
    records: list[Record],
    kind: str,
) -> dict[str, Record]:
    result: dict[str, Record] = {}

    for path, record in records:
        record_id = _required_string(
            record,
            "id",
            str(path),
        )

        if record_id in result:
            previous = result[record_id][0]

            raise ValueError(f"Duplicate {kind} ID {record_id}: {previous} and {path}")

        result[record_id] = (
            path,
            record,
        )

    return result


def _require_references(
    references: list[str],
    known: set[str],
    kind: str,
    context: str,
) -> None:
    missing = sorted(set(references) - known)

    if not missing:
        return

    raise ValueError(f"{context} references unknown {kind}: {', '.join(missing)}")


def _validate_capabilities(
    capabilities: dict[str, Record],
    requirement_ids: set[str],
) -> None:
    for capability_id, (
        path,
        capability,
    ) in capabilities.items():
        _require_references(
            _optional_string_list(
                capability,
                "requirements",
                str(path),
            ),
            requirement_ids,
            "requirements",
            capability_id,
        )


def _validate_graph(
    flow_id: str,
    flow: dict[str, JsonValue],
) -> None:
    steps = [
        _object(
            value,
            f"{flow_id}.steps",
        )
        for value in _array(
            flow["steps"],
            f"{flow_id}.steps",
        )
    ]

    terminals = [
        _object(
            value,
            f"{flow_id}.terminal_states",
        )
        for value in _array(
            flow["terminal_states"],
            f"{flow_id}.terminal_states",
        )
    ]

    step_ids = [
        _required_string(
            step,
            "id",
            flow_id,
        )
        for step in steps
    ]

    terminal_ids = [
        _required_string(
            terminal,
            "id",
            flow_id,
        )
        for terminal in terminals
    ]

    all_ids = [
        *step_ids,
        *terminal_ids,
    ]

    if len(all_ids) != len(set(all_ids)):
        raise ValueError(f"{flow_id} contains duplicate node IDs")

    entry = _required_string(
        flow,
        "entry",
        flow_id,
    )

    if entry not in set(step_ids):
        raise ValueError(f"{flow_id} entry {entry} is not a step")

    targets = set(all_ids)

    for step in steps:
        step_id = _required_string(
            step,
            "id",
            flow_id,
        )

        transitions = _object(
            step["transitions"],
            f"{flow_id}.{step_id}.transitions",
        )

        for outcome, value in transitions.items():
            target = _string(
                value,
                (f"{flow_id}.{step_id}.transitions.{outcome}"),
            )

            if target not in targets:
                raise ValueError(
                    f"{flow_id}.{step_id} transition {outcome} targets unknown node {target}"
                )


def _validate_flow_references(
    flow_id: str,
    flow: dict[str, JsonValue],
    requirement_ids: set[str],
    capability_ids: set[str],
    flow_ids: set[str],
) -> None:
    _require_references(
        _optional_string_list(
            flow,
            "requirements",
            flow_id,
        ),
        requirement_ids,
        "requirements",
        flow_id,
    )

    _require_references(
        _optional_string_list(
            flow,
            "capabilities",
            flow_id,
        ),
        capability_ids,
        "capabilities",
        flow_id,
    )

    for value in _array(
        flow["steps"],
        f"{flow_id}.steps",
    ):
        step = _object(
            value,
            f"{flow_id}.steps",
        )

        step_id = _required_string(
            step,
            "id",
            flow_id,
        )

        context = f"{flow_id}.{step_id}"

        _require_references(
            _optional_string_list(
                step,
                "requirements",
                context,
            ),
            requirement_ids,
            "requirements",
            context,
        )

        capability = _optional_string(
            step,
            "capability",
            context,
        )

        if capability is not None:
            _require_references(
                [capability],
                capability_ids,
                "capabilities",
                context,
            )

        subflow = _optional_string(
            step,
            "subflow",
            context,
        )

        if subflow is not None:
            _require_references(
                [subflow],
                flow_ids,
                "flows",
                context,
            )

    for value in _array(
        flow["terminal_states"],
        f"{flow_id}.terminal_states",
    ):
        terminal = _object(
            value,
            f"{flow_id}.terminal_states",
        )

        terminal_id = _required_string(
            terminal,
            "id",
            flow_id,
        )

        context = f"{flow_id}.{terminal_id}"

        capability = _optional_string(
            terminal,
            "capability",
            context,
        )

        if capability is not None:
            _require_references(
                [capability],
                capability_ids,
                "capabilities",
                context,
            )


def main() -> None:
    requirements = _index_records(
        _load_registry(
            SPEC / "requirements",
            "requirements",
            SCHEMA / "requirement.schema.json",
        ),
        "requirement",
    )

    capabilities = _index_records(
        _load_registry(
            SPEC / "capabilities",
            "capabilities",
            SCHEMA / "capability.schema.json",
        ),
        "capability",
    )

    flows = _index_records(
        _load_flows(),
        "flow",
    )

    requirement_ids = set(requirements)
    capability_ids = set(capabilities)
    flow_ids = set(flows)

    _validate_capabilities(
        capabilities,
        requirement_ids,
    )

    for flow_id, (_, flow) in flows.items():
        _validate_graph(
            flow_id,
            flow,
        )

        _validate_flow_references(
            flow_id,
            flow,
            requirement_ids,
            capability_ids,
            flow_ids,
        )

    print("Specification is valid.")


if __name__ == "__main__":
    main()
