"""LLM configuration constants.

Central settings for language model behavior.
"""

# Model selection - use the same model as claim_extractor for consistency
MODEL_NAME = "google_genai:gemini-2.5-flash"

# Temperature settings
DEFAULT_TEMPERATURE = 0.0  # Use for exact, consistent outputs (no randomness)
