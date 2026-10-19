"""Demucs connection: splits a film's sound into dialogue and everything else, on this computer.

Needs the optional install (`uv sync --group dubbing`), so nothing here imports it until a film
is actually separated. Model weights are kept in `data/cache/` (see `build_container`)."""

import importlib.util
from pathlib import Path
from typing import Any

from velvetdub.config.settings import Settings
from velvetdub.domain.dubbing import SeparatedStems
from velvetdub.errors import ConfigError, ProviderError
from velvetdub.providers.base import SourceSeparator
from velvetdub.providers.registry import separators

DEFAULT_MODEL = "htdemucs"
# The film is separated this many seconds at a time: a whole film at once would need many GB.
CHUNK_SECONDS = 300


class DemucsSeparator(SourceSeparator):
    name = "demucs"

    def separate(self, audio_path: Path, out_dir: Path) -> SeparatedStems:
        import numpy as np
        import soundfile
        import torch
        from demucs.apply import apply_model
        from demucs.pretrained import get_model

        out_dir.mkdir(parents=True, exist_ok=True)
        dialogue, background = out_dir / "dialogue.wav", out_dir / "background.wav"
        model = get_model(self.model or DEFAULT_MODEL)
        model.eval()
        rate = soundfile.info(str(audio_path)).samplerate
        if rate != model.samplerate:
            raise ProviderError(f"Demucs needs {model.samplerate} Hz audio, got {rate} Hz.")
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        voice = model.sources.index("vocals")

        def write(sink: Any, signal: Any) -> None:
            sink.write(np.clip(signal.cpu().numpy().T, -1.0, 1.0))

        with (
            soundfile.SoundFile(str(dialogue), "w", rate, 2, "PCM_16") as dialogue_out,
            soundfile.SoundFile(str(background), "w", rate, 2, "PCM_16") as background_out,
        ):
            for block in soundfile.blocks(
                str(audio_path), blocksize=CHUNK_SECONDS * rate, dtype="float32", always_2d=True
            ):
                wave = torch.from_numpy(block.T)
                mono = wave.mean(0)
                wave = (wave - mono.mean()) / (mono.std() + 1e-8)
                with torch.no_grad():
                    parts = apply_model(
                        model, wave[None], device=device, split=True, overlap=0.25, progress=False
                    )[0]
                parts = parts * (mono.std() + 1e-8) + mono.mean()
                write(dialogue_out, parts[voice])
                write(background_out, parts.sum(0) - parts[voice])
        return SeparatedStems(dialogue=dialogue, background=background)


@separators.register("demucs")
def _create(settings: Settings) -> SourceSeparator:
    if importlib.util.find_spec("demucs") is None:
        raise ConfigError("Dubbing needs an extra install. Run: uv sync --group dubbing")
    return DemucsSeparator(settings.separation_model)
