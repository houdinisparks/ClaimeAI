"""Unified LLM model instances and factory functions.

Provides access to configured language model instances for all modules.
"""

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel

from utils.settings import settings


def get_llm(
    model_name: str = "openai:gpt-5",
    temperature: float = 0.0,
    completions: int = 1,
) -> BaseChatModel:
    """Get LLM with specified configuration.

    Args:
        model_name: The model to use
        temperature: Temperature for generation
        completions: How many completions we need (affects temperature for diversity)

    Returns:
        Configured LLM instance
    """
    # Use higher temp when doing multiple completions for diversity
    if completions > 1 and temperature == 0.0:
        temperature = 0.2

    # Determine which API key to use based on model provider
    is_gemini = model_name.startswith("google_genai:")
    is_gpt_5 = "gpt-5" in model_name.lower()

    
    # All other models (Gemini, GPT-4, etc.) use standard configuration
    return init_chat_model(
        model=model_name,
        api_key=settings.gemini_api_key if is_gemini else settings.openai_api_key,
        temperature=temperature,
        model_kwargs={"reasoning_effort": "minimal"} if is_gpt_5 else {},
    )


def get_default_llm() -> BaseChatModel:
    """Get default LLM instance."""
    return get_llm()
