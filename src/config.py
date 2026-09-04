"""
Centralized configuration and environment loading.

Importing this module loads .env into environment variables as a side effect.
All other modules get env vars via `from src import config` at the top of the file.
"""
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


# --- Typed environment helpers ---------------------------------------------
#
# Every tunable constant in the system is read through these so a single .env
# (see .env.example) can override any of them without code changes. An unset or
# empty variable falls back to the provided default.

def env_str(name: str, default: str) -> str:
    """Read a string env var, falling back to default when unset or empty."""
    value = os.getenv(name)
    return value if value not in (None, "") else default


def env_int(name: str, default: int) -> int:
    """Read an int env var, falling back to default when unset, empty, or invalid."""
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    """Read a float env var, falling back to default when unset, empty, or invalid."""
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError:
        return default


def today_str() -> str:
    """Return today's date (UTC) as YYYY-MM-DD."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def date_prefix() -> str:
    """A short line stating today's date, prepended to LLM prompts so the model
    always reasons against the current date (e.g. RFP submission deadlines)."""
    return f"Today's date is {today_str()}.\n\n"


def get_groq_api_key() -> str:
    """Return the Groq API key. Raises if missing."""
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError(
            "GROQ_API_KEY not set. Add it to .env at the project root."
        )
    return key


# --- LLM provider selection ------------------------------------------------
#
# The active provider is chosen with the LLM_PROVIDER env var. All generation
# code calls config.get_llm() instead of instantiating a chat model directly,
# so switching providers is a one-line .env change.

# Per-provider default model, used when the caller doesn't pass one. For the
# "local" provider the model is intentionally empty: a typical OpenAI-compatible
# local server (Ollama, LM Studio, llama.cpp, vLLM) serves a single loaded model
# and ignores the field.
_DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "anthropic": "claude-opus-4-8",
    "openai": "gpt-4o",
    "gemini": "gemini-1.5-pro",
    "local": "",
}

# Env var holding the API key for each provider (local needs none).
_PROVIDER_KEY_ENV = {
    "groq": "GROQ_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "local": None,
}

# In-memory overrides set from the Admin page. These take precedence over the
# .env values for the running process only — they reset to the .env defaults on
# restart (we deliberately do not write secrets/config back to disk here).
_runtime: dict = {"provider": None, "model": None, "local_base_url": None}

_DEFAULT_LOCAL_BASE_URL = "http://localhost:11434/v1"


def get_llm_provider() -> str:
    """Return the active LLM provider — runtime override, else .env, else groq."""
    provider = _runtime["provider"] or os.getenv("LLM_PROVIDER", "groq")
    return provider.strip().lower()


def _local_base_url() -> str:
    return _runtime["local_base_url"] or os.getenv("LOCAL_BASE_URL", _DEFAULT_LOCAL_BASE_URL)


def admin_config() -> dict:
    """Snapshot of the LLM configuration for the Admin page."""
    provider = get_llm_provider()
    return {
        "provider": provider,
        "providers": list(_DEFAULT_MODELS),
        "default_models": _DEFAULT_MODELS,
        "model": _runtime["model"] or _DEFAULT_MODELS.get(provider, ""),
        "local_base_url": _local_base_url(),
        "configured": {
            name: (env is None or bool(os.getenv(env)))
            for name, env in _PROVIDER_KEY_ENV.items()
        },
    }


def set_admin_config(
    provider: str | None = None,
    model: str | None = None,
    local_base_url: str | None = None,
) -> dict:
    """
    Apply runtime LLM overrides (in-memory only).

    Switching provider without an explicit model resets the model override so the
    new provider's default is used. Raises ValueError on an unknown provider.
    """
    if provider is not None:
        provider = provider.strip().lower()
        if provider not in _DEFAULT_MODELS:
            raise ValueError(
                f"Unknown provider '{provider}'. Choose one of: {', '.join(_DEFAULT_MODELS)}."
            )
        if provider != get_llm_provider():
            _runtime["model"] = None  # fall back to the new provider's default
        _runtime["provider"] = provider

    if model is not None:
        _runtime["model"] = model.strip() or None

    if local_base_url is not None:
        _runtime["local_base_url"] = local_base_url.strip() or None

    return admin_config()


def get_llm(model: str | None = None, temperature: float | None = None):
    """
    Build a LangChain chat model for the configured provider.

    Args:
        model: Optional model identifier. When None, the provider's default
            model is used. Ignored for the local provider (left empty).
        temperature: Sampling temperature.

    Returns:
        A LangChain BaseChatModel instance.

    Raises:
        RuntimeError: If LLM_PROVIDER is unknown or its package is missing.
    """
    provider = get_llm_provider()

    if temperature is None:
        temperature = env_float("LLM_TEMPERATURE", 0.0)

    if provider not in _DEFAULT_MODELS:
        raise RuntimeError(
            f"Unknown LLM_PROVIDER '{provider}'. "
            f"Choose one of: {', '.join(_DEFAULT_MODELS)}."
        )

    if model is None:
        model = _runtime["model"] or env_str("LLM_MODEL", "") or _DEFAULT_MODELS[provider]

    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(model=model, temperature=temperature)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, temperature=temperature)

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, temperature=temperature)

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=model, temperature=temperature)

    if provider == "local":
        # OpenAI-compatible local server. Model is left empty on purpose;
        # the server uses whatever model it has loaded. base_url points at the
        # local endpoint, and the api key is usually a placeholder.
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model or "",
            temperature=temperature,
            base_url=_local_base_url(),
            api_key=os.getenv("LOCAL_API_KEY", "not-needed"),
        )

    # Unreachable: provider already validated above.
    raise RuntimeError(f"Unhandled provider '{provider}'.")
