"""Read and write pydantic models as JSON files. Writes are atomic."""

import os
from pathlib import Path

from pydantic import BaseModel


def read_model[M: BaseModel](path: Path, model: type[M]) -> M:
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def write_model(path: Path, value: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(value.model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp, path)
