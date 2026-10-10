"""The ordered stage lists.

Phase 2 (dubbing) adds stages here (separate, synthesize, mix) without touching the runner or
the stages above.
"""

from velvetdub.pipeline.stage import Stage
from velvetdub.pipeline.stages.build_filters import BuildFiltersStage
from velvetdub.pipeline.stages.extract_audio import ExtractAudioStage
from velvetdub.pipeline.stages.subtitles import SubtitlesStage
from velvetdub.pipeline.stages.transcribe import TranscribeStage
from velvetdub.pipeline.stages.translate import TranslateStage
from velvetdub.pipeline.stages.visual_scan import VisualScanStage


def phase1_stages() -> list[Stage]:
    return [
        ExtractAudioStage(),
        TranscribeStage(),
        VisualScanStage(),
        TranslateStage(),
        BuildFiltersStage(),
        SubtitlesStage(),
    ]
