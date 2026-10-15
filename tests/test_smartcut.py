"""Planning a smart cut: which stretches are copied and which are encoded again."""

import pytest

from velvetdub.domain.smartcut import (
    Piece,
    VideoTiming,
    audio_spans,
    frame_ranges,
    plan_pieces,
)

# 10 fps, so frame n is shown at n / 10 s; the picture starts 2 frames in, like a film with
# B-frames. 1000 frames in all.
TIMING = VideoTiming(start=0.2, frame_duration=0.1, frame_count=1000)
KEYFRAMES = list(range(0, 1000, 50))  # a keyframe every 5 s


def copy(first: int, frames: int) -> Piece:
    return Piece(kind="copy", first_frame=first, frames=frames)


def encode(first: int, frames: int) -> Piece:
    return Piece(kind="encode", first_frame=first, frames=frames)


# --- from times to frames ----------------------------------------------------------------


def test_a_time_is_the_first_frame_shown_at_or_after_it() -> None:
    assert TIMING.frame_at_or_after(0.2) == 0
    assert TIMING.frame_at_or_after(0.21) == 1
    assert TIMING.frame_at_or_after(10.2) == 100
    assert TIMING.frame_at_or_after(10.1999999) == 100  # float noise is not a frame
    assert TIMING.frame_at_or_after(10.20000001) == 100  # a ten-millionth of a frame late
    assert TIMING.frame_at_or_after(10.2001) == 101  # a thousandth of a frame late is the next


def test_times_before_the_start_or_after_the_end_are_clamped() -> None:
    assert TIMING.frame_at_or_after(-5) == 0
    assert TIMING.frame_at_or_after(0.0) == 0
    assert TIMING.frame_at_or_after(5000) == 1000


def test_kept_stretches_become_frame_ranges_and_empty_ones_vanish() -> None:
    ranges = frame_ranges([(0.0, 10.2), (20.2, 20.2), (30.2, 1000.0)], TIMING)
    assert ranges == [(0, 100), (300, 1000)]


def test_the_sound_keeps_exactly_the_stretches_the_picture_does() -> None:
    (span,) = audio_spans([(100, 300)], TIMING)
    assert span[0] == pytest.approx(10.2)  # frame 100
    assert span[1] == pytest.approx(30.2)  # up to the frame after, which is not itself kept


# --- splitting into copied and encoded pieces --------------------------------------------


def test_a_stretch_between_keyframes_is_copied_and_only_its_ends_are_encoded() -> None:
    pieces = plan_pieces([(120, 430)], KEYFRAMES, 1000)
    assert pieces == [encode(120, 30), copy(150, 250), encode(400, 30)]
    assert sum(p.frames for p in pieces) == 430 - 120


def test_a_stretch_that_starts_or_ends_on_a_keyframe_needs_no_encoded_end() -> None:
    assert plan_pieces([(150, 400)], KEYFRAMES, 1000) == [copy(150, 250)]
    assert plan_pieces([(120, 400)], KEYFRAMES, 1000) == [encode(120, 30), copy(150, 250)]
    assert plan_pieces([(150, 430)], KEYFRAMES, 1000) == [copy(150, 250), encode(400, 30)]


def test_a_stretch_shorter_than_a_group_of_pictures_is_encoded_whole() -> None:
    assert plan_pieces([(110, 140)], KEYFRAMES, 1000) == [encode(110, 30)]
    # even when a keyframe falls inside it, there is no whole group to copy
    assert plan_pieces([(140, 160)], KEYFRAMES, 1000) == [encode(140, 20)]


def test_the_start_of_the_film_is_copied_from_its_first_keyframe() -> None:
    assert plan_pieces([(0, 230)], KEYFRAMES, 1000) == [copy(0, 200), encode(200, 30)]


def test_the_last_stretch_is_copied_to_the_end_of_the_film() -> None:
    assert plan_pieces([(620, 1000)], KEYFRAMES, 1000) == [encode(620, 30), copy(650, 350)]


def test_a_film_with_no_keyframes_inside_a_stretch_is_encoded() -> None:
    assert plan_pieces([(10, 40)], [0], 1000) == [encode(10, 30)]


def test_several_stretches_are_planned_in_order() -> None:
    pieces = plan_pieces([(0, 100), (120, 430), (900, 1000)], KEYFRAMES, 1000)
    assert pieces == [
        copy(0, 100),
        encode(120, 30),
        copy(150, 250),
        encode(400, 30),
        copy(900, 100),
    ]


def test_every_frame_to_keep_is_in_exactly_one_piece() -> None:
    ranges = [(7, 93), (101, 399), (401, 402), (450, 1000)]
    pieces = plan_pieces(ranges, KEYFRAMES, 1000)
    covered = [f for p in pieces for f in range(p.first_frame, p.first_frame + p.frames)]
    wanted = [f for first, stop in ranges for f in range(first, stop)]
    assert covered == wanted


def test_copied_pieces_always_begin_on_a_keyframe_and_end_on_one_or_the_film_end() -> None:
    ranges = [(7, 93), (101, 399), (450, 1000), (3, 977)]
    for piece in plan_pieces(ranges, KEYFRAMES, 1000):
        if piece.kind == "copy":
            assert piece.first_frame in KEYFRAMES
            end = piece.first_frame + piece.frames
            assert end in KEYFRAMES or end == 1000
