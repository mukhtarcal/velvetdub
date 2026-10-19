"""The ordered stage lists.

Adding a step means adding a `Stage` here; the runner and the stages around it are untouched.
The dubbing stages do nothing (and cost nothing) unless a dub language was asked for.
"""

from velvetdub.pipeline.stage import Stage
from velvetdub.pipeline.stages.build_filters import BuildFiltersStage
from velvetdub.pipeline.stages.dub_mix import DubMixStage
from velvetdub.pipeline.stages.dub_speech import DubSpeechStage
from velvetdub.pipeline.stages.dub_transcribe import DubTranscribeStage
from velvetdub.pipeline.stages.dub_translate import DubTranslateStage
from velvetdub.pipeline.stages.dub_voices import DubVoicesStage
from velvetdub.pipeline.stages.extract_audio import ExtractAudioStage
from velvetdub.pipeline.stages.separate import SeparateStage
from velvetdub.pipeline.stages.subtitles import SubtitlesStage
from velvetdub.pipeline.stages.transcribe import TranscribeStage
from velvetdub.pipeline.stages.translate import TranslateStage
from velvetdub.pipeline.stages.visual_scan import VisualScanStage


def phase1_stages() -> list[Stage]:
    """Filters and subtitles."""
    return [
        ExtractAudioStage(),
        TranscribeStage(),
        VisualScanStage(),
        TranslateStage(),
        BuildFiltersStage(),
        SubtitlesStage(),
    ]


def dubbing_stages() -> list[Stage]:
    """Voices, script, speech and mix, for each dub language asked for."""
    return [
        SeparateStage(),
        DubTranscribeStage(),
        DubTranslateStage(),
        DubVoicesStage(),
        DubSpeechStage(),
        DubMixStage(),
    ]


def all_stages() -> list[Stage]:
    return [*phase1_stages(), *dubbing_stages()]
