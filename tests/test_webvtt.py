from velvetdub.subtitles.webvtt import Cue, format_timestamp, format_webvtt


def test_timestamp_formatting() -> None:
    assert format_timestamp(0) == "00:00:00.000"
    assert format_timestamp(3661.5) == "01:01:01.500"
    assert format_timestamp(-1) == "00:00:00.000"


def test_webvtt_document() -> None:
    out = format_webvtt([Cue(start=1, end=2.5, text="Hi")])
    assert out == "WEBVTT\n\n00:00:01.000 --> 00:00:02.500\nHi\n"
