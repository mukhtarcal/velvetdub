"""Claude connection: sends a prompt and returns the structured answer.

Only vendor mechanics live here. The translation rules and checks belong to
`velvetdub.features.translation`."""

import anthropic
from pydantic import BaseModel

from velvetdub.config.settings import Settings
from velvetdub.errors import ProviderError
from velvetdub.providers.base import TextGenerator
from velvetdub.providers.keys import require_key
from velvetdub.providers.registry import text_generators

MAX_OUTPUT_TOKENS = 16000


class AnthropicTextGenerator(TextGenerator):
    name = "anthropic"

    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        super().__init__(model)
        self._client = client

    def generate[T: BaseModel](self, system: str, prompt: str, schema: type[T]) -> T:
        """The only method that talks to the network (tests replace it)."""
        response = self._client.messages.parse(
            model=self.model or "",
            max_tokens=MAX_OUTPUT_TOKENS,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
        if response.stop_reason == "refusal":
            raise ProviderError("Claude declined to answer this request.")
        if response.parsed_output is None:
            raise ProviderError("Claude returned no usable answer.")
        return response.parsed_output


@text_generators.register("anthropic")
def _create(settings: Settings) -> TextGenerator:
    key = require_key(settings.anthropic_api_key, "ANTHROPIC_API_KEY")
    return AnthropicTextGenerator(anthropic.Anthropic(api_key=key), settings.translation_model)
