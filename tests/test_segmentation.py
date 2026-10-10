from velvetdub.providers.segmentation import RawWord, build_segments


def words(*specs: tuple[str, float, float, str | None]) -> list[RawWord]:
    return [RawWord(text=t, start=s, end=e, speaker=sp) for t, s, e, sp in specs]


def test_sentence_end_closes_a_line() -> None:
    segs = build_segments(
        words(("Hello", 0, 0.5, "A"), ("there.", 0.5, 1.2, "A"), ("Bye", 1.3, 1.6, "A"))
    )
    assert [s.text for s in segs] == ["Hello there.", "Bye"]
    assert [s.id for s in segs] == ["s0", "s1"]


def test_speaker_change_starts_a_new_line() -> None:
    segs = build_segments(words(("Hi", 0, 0.3, "A"), ("Hey", 0.4, 0.7, "B")))
    assert [(s.speaker, s.text) for s in segs] == [("A", "Hi"), ("B", "Hey")]


def test_long_pause_starts_a_new_line() -> None:
    segs = build_segments(words(("Wait", 0, 0.4, "A"), ("okay", 3.0, 3.4, "A")))
    assert len(segs) == 2


def test_long_runs_are_split_for_readability() -> None:
    many = words(*[(f"w{i}", i * 0.5, i * 0.5 + 0.4, "A") for i in range(30)])
    segs = build_segments(many, max_duration=7.0)
    assert len(segs) >= 2
    assert all(s.duration <= 7.5 for s in segs)
    assert sum(len(s.words) for s in segs) == 30  # nothing lost


def test_word_timing_is_preserved_for_exact_muting() -> None:
    (seg,) = build_segments(words(("Damn", 1.25, 1.6, "A")))
    assert (seg.words[0].start, seg.words[0].end) == (1.25, 1.6)


def test_short_sentence_does_not_fragment_into_tiny_lines() -> None:
    segs = build_segments(words(("No.", 0, 0.3, "A"), ("Stop.", 0.4, 0.8, "A")))
    assert len(segs) == 1  # each ends a sentence but neither has lasted a second yet


def test_empty_input() -> None:
    assert build_segments([]) == []
