from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from src.core.config import Config

from src.core.config import config


class ModelManager:
    def __init__(self, config: "Config") -> None:
        self.config = config
        self.provider_manager = config.provider_manager

    def resolve_model(self, model: str) -> Tuple[str, str]:
        """Resolve model name to (provider, actual_model)

        Parses provider prefixes and passes through model names unchanged
        when no provider is specified.

        Returns:
            Tuple[str, str]: (provider_name, actual_model_name)
        """
        # Parse provider prefix
        provider_name, actual_model = self.provider_manager.parse_model_name(model)

        # No model mapping needed - pass through the model name as-is
        return provider_name, actual_model


model_manager = ModelManager(config)
