"""A pipeline stage: reads input files, writes output files.

A stage is skipped when its recorded fingerprint still matches. The fingerprint covers the input
files (size and mtime) and `config_key` (provider, model, options), so changing either re-runs
the stage and everything downstream of it.

To add a stage (such as the Phase 2 dubbing steps): subclass Stage and add it to the list in
`velvetdub.pipeline.stages`.
"""

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from velvetdub.errors import MissingInputError
from velvetdub.pipeline.context import PipelineContext


class Stage(ABC):
    name: ClassVar[str]

    @abstractmethod
    def inputs(self, ctx: PipelineContext) -> list[Path]: ...

    @abstractmethod
    def outputs(self, ctx: PipelineContext) -> list[Path]: ...

    @abstractmethod
    def run(self, ctx: PipelineContext) -> None: ...

    def config_key(self, ctx: PipelineContext) -> str:
        """Anything besides input files that changes this stage's output."""
        return ""

    def fingerprint(self, ctx: PipelineContext) -> str:
        digest = hashlib.sha256(self.config_key(ctx).encode())
        for path in self.inputs(ctx):
            if not path.exists():
                raise MissingInputError(f"{self.name}: missing input {path.name}")
            stat = path.stat()
            digest.update(f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}".encode())
        return digest.hexdigest()

    def outputs_exist(self, ctx: PipelineContext) -> bool:
        return all(path.exists() for path in self.outputs(ctx))
