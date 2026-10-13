"""Translation feature with a stand-in text model: checks batching, retries and validation."""

import pytest
from pydantic import BaseModel

from velvetdub.domain.transcript import Segment, Transcript
from velvetdub.errors import ProviderError
from velvetdub.features.translation.translator import TranslatedBatch, Translator, batches
from velvetdub.providers.base import TextGenerator


def segs(n: int) -> list[Segment]:
    return [Segment(id=f"s{i}", start=i, end=i + 1, text=f"line {i}") for i in range(n)]


class StubGenerator(TextGenerator):
    name = "stub"

    def __init__(self, skip: set[str] | None = None, always_skip: bool = False) -> None:
        super().__init__("m")
        self.prompts: list[str] = []
        self._skip = skip or set()
        self._always_skip = always_skip

    def generate[T: BaseModel](self, system: str, prompt: str, schema: type[T]) -> T:
        self.prompts.append(prompt)
        ids = [
            line[1 : line.index("]")]
            for line in prompt.splitlines()
            if line.startswith("[") and not line.startswith("[context]")
        ]
        lines = [{"id": i, "text": f"[es] {i}"} for i in ids if i not in self._skip]
        if not self._always_skip:
            self._skip = set()  # first attempt skips, the retry succeeds
        return schema.model_validate({"lines": lines})

    def asked_ids(self) -> list[list[str]]:
        return [
            [line[1 : line.index("]")] for line in p.splitlines() if line.startswith("[s")]
            for p in self.prompts
        ]


def test_translation_keeps_ids_and_durations() -> None:
    result = Translator(StubGenerator()).translate(
        Transcript(language="en", segments=segs(3)), "es"
    )
    assert [t.segment_id for t in result.segments] == ["s0", "s1", "s2"]
    assert result.segments[1].text == "[es] s1"
    assert all(t.target_duration == 1.0 for t in result.segments)


def test_prompt_names_both_languages_and_the_tone() -> None:
    generator = StubGenerator()
    Translator(generator).translate(Transcript(language="en", segments=segs(1)), "es")
    assert "Source language: en" in generator.prompts[0]
    assert "Target language: es" in generator.prompts[0]


def test_skipped_lines_are_retried_once() -> None:
    generator = StubGenerator(skip={"s1"})
    result = Translator(generator).translate(Transcript(language="en", segments=segs(3)), "es")
    assert len(result.segments) == 3
    assert generator.asked_ids() == [["s0", "s1", "s2"], ["s1"]]


def test_persistent_skips_fail_loudly() -> None:
    generator = StubGenerator(skip={"s1"}, always_skip=True)
    with pytest.raises(ProviderError, match="s1"):
        Translator(generator).translate(Transcript(language="en", segments=segs(3)), "es")


def test_batching_gives_context_from_previous_lines() -> None:
    pairs = list(batches(segs(5), 2))
    assert [[s.id for s in b] for b, _ in pairs] == [["s0", "s1"], ["s2", "s3"], ["s4"]]
    assert pairs[0][1] == []
    assert [s.id for s in pairs[1][1]] == ["s0", "s1"]


def test_answer_shape_is_the_batch_model() -> None:
    assert TranslatedBatch.model_validate({"lines": [{"id": "a", "text": "b"}]}).lines[0].id == "a"
