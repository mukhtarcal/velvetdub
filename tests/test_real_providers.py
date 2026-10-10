"""Real providers with the network call replaced. Everything around the call is real."""

from collections.abc import Sequence
from pathlib import Path

import pytest

from velvetdub.domain.filtering import FilterCategory, Severity
from velvetdub.domain.transcript import Segment, Transcript
from velvetdub.domain.translation import TranslationTone
from velvetdub.errors import ProviderError
from velvetdub.providers.anthropic import AnthropicTranslator, batches
from velvetdub.providers.assemblyai import AssemblyAITranscriber, RawTranscription
from velvetdub.providers.gemini import (
    ClipResult,
    Detection,
    GeminiModerator,
    VisualCategory,
    parse_clock,
)
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


# --- Claude translation ------------------------------------------------------------------


def segs(n: int) -> list[Segment]:
    return [Segment(id=f"s{i}", start=i, end=i + 1, text=f"line {i}") for i in range(n)]


class StubTranslator(AnthropicTranslator):
    def __init__(self, skip: set[str] | None = None, always_skip: bool = False) -> None:
        super().__init__(client=None, model="m")  # type: ignore[arg-type]
        self.calls: list[list[str]] = []
        self._skip = skip or set()
        self._always_skip = always_skip

    def _translate_batch(
        self,
        batch: Sequence[Segment],
        context: Sequence[Segment],
        source_language: str,
        target_language: str,
        tone: TranslationTone,
    ) -> dict[str, str]:
        self.calls.append([s.id for s in batch])
        out = {s.id: f"[{target_language}] {s.text}" for s in batch if s.id not in self._skip}
        if not self._always_skip:
            self._skip = set()  # first attempt skips, the retry succeeds
        return out


def test_translation_keeps_ids_and_durations() -> None:
    transcript = Transcript(language="en", segments=segs(3))
    result = StubTranslator().translate(transcript, "es")
    assert [t.segment_id for t in result.segments] == ["s0", "s1", "s2"]
    assert result.segments[1].text == "[es] line 1"
    assert all(t.target_duration == 1.0 for t in result.segments)


def test_skipped_lines_are_retried_once() -> None:
    translator = StubTranslator(skip={"s1"})
    result = translator.translate(Transcript(language="en", segments=segs(3)), "es")
    assert len(result.segments) == 3
    assert translator.calls == [["s0", "s1", "s2"], ["s1"]]


def test_persistent_skips_fail_loudly() -> None:
    translator = StubTranslator(skip={"s1"}, always_skip=True)
    with pytest.raises(ProviderError, match="s1"):
        translator.translate(Transcript(language="en", segments=segs(3)), "es")


def test_batching_gives_context_from_previous_lines() -> None:
    pairs = list(batches(segs(5), 2))
    assert [[s.id for s in b] for b, _ in pairs] == [["s0", "s1"], ["s2", "s3"], ["s4"]]
    assert pairs[0][1] == []
    assert [s.id for s in pairs[1][1]] == ["s0", "s1"]


# --- Gemini ------------------------------------------------------------------------------


class StubModerator(GeminiModerator):
    def __init__(self, result: ClipResult) -> None:
        super().__init__(client=None, model="gemini-x")  # type: ignore[arg-type]
        self._result = result

    def _analyse_clip(self, clip_path: Path) -> ClipResult:
        return self._result


def detection(
    start: str, end: str, category: VisualCategory = VisualCategory.VIOLENCE
) -> Detection:
    return Detection(
        start=start, end=end, category=category, severity="strong", confidence=0.9, description="d"
    )


def test_detections_are_shifted_onto_the_film_timeline(tmp_path: Path) -> None:
    moderator = StubModerator(ClipResult(detections=[detection("01:05", "01:20")]))
    (event,) = moderator.scan_clip(tmp_path / "c.mp4", offset=600)
    assert (event.start, event.end) == (665.0, 680.0)
    assert event.category is FilterCategory.VIOLENCE
    assert event.severity is Severity.STRONG
    assert event.source == "gemini:gemini-x"


def test_backwards_range_is_repaired_not_dropped(tmp_path: Path) -> None:
    moderator = StubModerator(ClipResult(detections=[detection("00:30", "00:10")]))
    (event,) = moderator.scan_clip(tmp_path / "c.mp4", offset=0)
    assert event.start == event.end == 30.0


def test_confidence_is_clamped(tmp_path: Path) -> None:
    found = detection("00:01", "00:02")
    found.confidence = 7
    (event,) = StubModerator(ClipResult(detections=[found])).scan_clip(tmp_path / "c.mp4", offset=0)
    assert event.confidence == 1.0


@pytest.mark.parametrize(
    ("text", "seconds"), [("00:07", 7), ("1:02:03", 3723), ("90", 90), (" 02:30 ", 150)]
)
def test_parse_clock(text: str, seconds: float) -> None:
    assert parse_clock(text) == seconds


def test_parse_clock_rejects_garbage() -> None:
    with pytest.raises(ProviderError):
        parse_clock("soon")
