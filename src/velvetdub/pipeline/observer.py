"""Progress reporting. The CLI prints it; the API can stream it later."""

from abc import ABC, abstractmethod


class PipelineObserver(ABC):
    @abstractmethod
    def stage_started(self, stage: str) -> None: ...

    @abstractmethod
    def stage_skipped(self, stage: str) -> None: ...

    @abstractmethod
    def stage_finished(self, stage: str) -> None: ...

    @abstractmethod
    def stage_failed(self, stage: str, error: str) -> None: ...


class NullObserver(PipelineObserver):
    def stage_started(self, stage: str) -> None:
        pass

    def stage_skipped(self, stage: str) -> None:
        pass

    def stage_finished(self, stage: str) -> None:
        pass

    def stage_failed(self, stage: str, error: str) -> None:
        pass
