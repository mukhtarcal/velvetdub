"""How dialogue is translated into subtitles. Vendor-neutral: any text model gets these rules."""

from velvetdub.domain.translation import TranslationTone

SYSTEM_PROMPT = """You translate film and TV dialogue into subtitles.

Rules:
- Translate each numbered line on its own. Never merge, split, reorder or drop lines.
- Return every id exactly once, with the translated text for that line.
- Keep the speaker's meaning, register and emotional force. Keep names unchanged.
- Keep profanity at the same strength as the original; do not censor or soften it unless the
  tone below says so. A separate system handles filtering.
- Write natural, speakable text, not a word-for-word copy.
- Lines marked as context are for understanding only; do not translate or return them."""

TONE_INSTRUCTIONS: dict[TranslationTone, str] = {
    TranslationTone.LITERAL: "Stay close to the original wording.",
    TranslationTone.NATURAL: "Prefer the way people really talk in the target language.",
    TranslationTone.KID_FRIENDLY: (
        "Use gentle, child-appropriate wording. Replace swearing and crude language with mild "
        "alternatives."
    ),
}

# Added when the lines will be spoken aloud over the film (a dub) rather than read as subtitles.
DUBBING_RULES = """
These lines will be spoken aloud by a voice actor over the original performance.
- Each line shows, in brackets, the seconds the original took. Write text a voice can say
  naturally in about that time: tighter if the target language runs long, never padded.
- Write numbers, units and abbreviations as words, the way they are said."""
