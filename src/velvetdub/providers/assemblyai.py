"""AssemblyAI transcription: word-level timestamps plus speaker labels in one call."""

from dataclasses import dataclass
from pathlib import Path

import assemblyai as aai

from velvetdub.config.settings import Settings
from velvetdub.domain.transcript import Transcript
from velvetdub.errors import ProviderError
from velvetdub.providers.base import Transcriber
from velvetdub.providers.keys import require_key
from velvetdub.providers.registry import transcribers
from velvetdub.providers.segmentation import RawWord, build_segments


@dataclass(frozen=True)
class RawTranscription:
    words: list[RawWord]
    language: str


class AssemblyAITranscriber(Transcriber):
    name = "assemblyai"

    def __init__(self, api_key: str, model: str | None = None) -> None:
        super().__init__(model)
        self._api_key = api_key

    def transcribe(self, audio_path: Path, language: str | None = None) -> Transcript:
        raw = self._fetch(audio_path, language)
        if not raw.words:
            raise ProviderError("AssemblyAI found no speech in the audio.")
        return Transcript(language=raw.language, segments=build_segments(raw.words))

    def _fetch(self, audio_path: Path, language: str | None) -> RawTranscription:
        """The only method that talks to the network (tests replace it)."""
        aai.settings.api_key = self._api_key
        config = aai.TranscriptionConfig(
            speaker_labels=True,
            punctuate=True,
            format_text=True,
            language_code=language,
            language_detection=language is None,
            speech_models=[self.model] if self.model else None,
        )
        result = aai.Transcriber(config=config).transcribe(str(audio_path))
        if result.status == aai.TranscriptStatus.error:
            raise ProviderError(f"AssemblyAI transcription failed: {result.error}")

        detected = (result.json_response or {}).get("language_code") or language or "en"
        words = [
            RawWord(
                text=w.text,
                start=w.start / 1000,
                end=w.end / 1000,
                speaker=w.speaker,
                confidence=w.confidence,
            )
            for w in (result.words or [])
        ]
        return RawTranscription(words=words, language=str(detected).split("_")[0].lower())


@transcribers.register("assemblyai")
def _create(settings: Settings) -> Transcriber:
    key = require_key(settings.assemblyai_api_key, "ASSEMBLYAI_API_KEY")
    return AssemblyAITranscriber(key, settings.transcription_model)
