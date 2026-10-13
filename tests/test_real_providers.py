"""Vendor connections with the network call replaced. Everything around the call is real."""

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

from velvetdub.errors import ProviderError, QuotaExceededError
from velvetdub.providers.assemblyai import AssemblyAITranscriber, RawTranscription
from velvetdub.providers.gemini import GeminiVideoAnalyzer
from velvetdub.providers.segmentation import RawWord

# --- AssemblyAI ---------------------------------------------------------------------------


class StubTranscriber(AssemblyAITranscriber):
    def __init__(self, raw: RawTranscription) -> None:
        super().__init__(api_key="x")
        self._raw = raw

    def _fetch(self, audio_path: Path, language: str | None) -> RawTranscription:
        return self._raw


def test_transcriber_builds_segments_from_words(tmp_path: Path) -> None:
    raw = RawTranscription(
        words=[RawWord("Hello", 0, 0.5, "A"), RawWord("world.", 0.5, 1.5, "A")], language="en"
    )
    transcript = StubTranscriber(raw).transcribe(tmp_path / "a.m4a")
    assert transcript.language == "en"
    assert [s.text for s in transcript.segments] == ["Hello world."]


def test_transcriber_rejects_silence(tmp_path: Path) -> None:
    with pytest.raises(ProviderError, match="no speech"):
        StubTranscriber(RawTranscription(words=[], language="en")).transcribe(tmp_path / "a.m4a")


# --- Gemini connection --------------------------------------------------------------------


class Answer(BaseModel):
    ok: bool


class StubAnalyzer(GeminiVideoAnalyzer):
    def __init__(self, calls: Callable[[], Answer]) -> None:
        super().__init__(client=None, model="gemini-x")  # type: ignore[arg-type]
        self._calls = calls

    def _analyze_once[T: BaseModel](self, clip_path: Path, instructions: str, schema: type[T]) -> T:
        return schema.model_validate(self._calls().model_dump())


def test_dropped_connections_are_retried(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("velvetdub.providers.gemini.CONNECTION_RETRY_SECONDS", 0)
    calls = 0

    def flaky() -> Answer:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.")
        return Answer(ok=True)

    assert StubAnalyzer(flaky).analyze_clip(tmp_path / "c.mp4", "look", Answer).ok
    assert calls == 3


def test_used_up_quota_stops_at_once_and_says_when_to_retry(tmp_path: Path) -> None:
    calls = 0

    def limited() -> Answer:
        nonlocal calls
        calls += 1
        raise genai_errors.ClientError(
            429,
            {"error": {"status": "RESOURCE_EXHAUSTED", "details": [{"retryDelay": "9294s"}]}},
        )

    with pytest.raises(QuotaExceededError) as info:
        StubAnalyzer(limited).analyze_clip(tmp_path / "c.mp4", "look", Answer)
    assert calls == 1
    assert info.value.retry_after_seconds == 9294
    assert "2 h 34 min" in str(info.value)


# --- Gemini streamed answer ----------------------------------------------------------------


class FakeChunk:
    def __init__(self, text: str | None = None, usage: object = None, block: str | None = None):
        self.text = text
        self.usage_metadata = usage
        self.prompt_feedback = (
            types.GenerateContentResponsePromptFeedback(block_reason=block) if block else None
        )


class FakeClient:
    """Just enough of the Gemini client: upload, status, streamed answer, delete."""

    def __init__(self, chunks: list[FakeChunk]) -> None:
        self.deleted: list[str] = []
        self.files = self
        self.models = self
        self._chunks = chunks

    def upload(self, file: Path) -> types.File:
        return types.File(name="files/x")

    def get(self, name: str) -> types.File:
        return types.File(name=name, state=types.FileState.ACTIVE)

    def delete(self, name: str) -> None:
        self.deleted.append(name)

    def generate_content_stream(self, **kwargs: object) -> list[FakeChunk]:
        return self._chunks


def analyzer_for(chunks: list[FakeChunk]) -> tuple[GeminiVideoAnalyzer, FakeClient]:
    client = FakeClient(chunks)
    return GeminiVideoAnalyzer(client=client, model="gemini-x"), client  # type: ignore[arg-type]


def test_streamed_pieces_are_joined_parsed_and_counted(tmp_path: Path) -> None:
    usage = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=1000, candidates_token_count=20, thoughts_token_count=5
    )
    analyzer, client = analyzer_for([FakeChunk('{"o'), FakeChunk('k": true}', usage=usage)])
    assert analyzer.analyze_clip(tmp_path / "c.mp4", "look", Answer).ok
    assert (analyzer.last_usage.input_tokens, analyzer.last_usage.output_tokens) == (1000, 25)
    assert client.deleted == ["files/x"]  # the clip is not left on the service


def test_unreadable_answer_is_a_clear_error(tmp_path: Path) -> None:
    analyzer, client = analyzer_for([FakeChunk("not json")])
    with pytest.raises(ProviderError, match="no usable result"):
        analyzer.analyze_clip(tmp_path / "c.mp4", "look", Answer)
    assert client.deleted == ["files/x"]


def test_blocked_clip_is_reported(tmp_path: Path) -> None:
    analyzer, _ = analyzer_for([FakeChunk(block="PROHIBITED_CONTENT")])
    with pytest.raises(ProviderError, match="blocked"):
        analyzer.analyze_clip(tmp_path / "c.mp4", "look", Answer)
