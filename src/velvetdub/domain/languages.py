"""Language names. Models are told the name, not just the code, because a code can't say which
variety to write: "ar" alone gets spoken Gulf Arabic, which a Modern Standard voice reads oddly."""

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ar": "Arabic",
    "ur": "Urdu",
    "hi": "Hindi",
    "tr": "Turkish",
    "ru": "Russian",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
}

# What to ask a model for, where plain "Arabic" is not enough.
_VARIETY: dict[str, str] = {
    "ar": "Modern Standard Arabic (Fusha), not a spoken dialect",
}


def language_name(code: str) -> str:
    """ "Arabic" for "ar"; the code itself when the language is not listed."""
    return LANGUAGE_NAMES.get(code, code)


def language_for_model(code: str) -> str:
    """How to name the language to a text model: the code, plus the variety when it matters."""
    variety = _VARIETY.get(code)
    return f"{code} ({variety})" if variety else code
