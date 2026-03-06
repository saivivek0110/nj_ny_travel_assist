"""
Configuration settings for Travel Agent for Work
Centralized configuration for API keys, LLM settings, and agent behavior
"""
import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

try:
    from langchain_mistralai import ChatMistralAI
    _mistral_available = True
except ImportError:
    _mistral_available = False

try:
    from langchain_cohere import ChatCohere
    _cohere_available = True
except ImportError:
    _cohere_available = False

# Load environment variables
load_dotenv()


def _handle_llm_error(e: Exception) -> None:
    """Translate common HTTP/API errors into friendly messages and re-raise."""
    msg = str(e).lower()
    if "429" in msg or "rate_limit" in msg or "resource_exhausted" in msg:
        raise RuntimeError(
            "⚠️  Rate limit hit (HTTP 429). "
            "You've exceeded your free quota. Wait a moment or switch models in .env."
        ) from e
    if "401" in msg or "unauthorized" in msg or "invalid api key" in msg or "authentication" in msg:
        raise RuntimeError(
            "🔑  Auth failed (HTTP 401). "
            "Check that LLM_API_KEY (or your provider's key) in .env is correct."
        ) from e
    if "403" in msg or "forbidden" in msg or "permission" in msg:
        raise RuntimeError(
            "🚫  Access denied (HTTP 403). "
            "Your API key may not have access to this model."
        ) from e
    if "404" in msg or "not found" in msg or "model not found" in msg:
        raise RuntimeError(
            "❓  Model not found (HTTP 404). "
            "Check that LLM_MODEL in .env is a valid model name."
        ) from e
    if "503" in msg or "502" in msg or "service unavailable" in msg or "overloaded" in msg:
        raise RuntimeError(
            "🔌  Provider is temporarily unavailable (HTTP 5xx). "
            "Try again in a moment."
        ) from e
    raise e  # Unknown error — re-raise as-is


class Config:
    """Centralized configuration for the Travel Agent"""

    # ============= API KEYS =============
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
    COHERE_API_KEY = os.getenv("COHERE_API_KEY")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")
    GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "token.json")

    # ============= LLM CONFIGURATION =============
    # Option A — Unified (recommended): set LLM_MODEL + LLM_API_KEY, provider auto-detected
    LLM_MODEL = os.getenv("LLM_MODEL")
    LLM_API_KEY = os.getenv("LLM_API_KEY")

    # Option B — Explicit provider (legacy, still works)
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "claude")

    # Model configurations (used with Option B)
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))

    # ============= AGENT BEHAVIOR =============
    VERBOSE = os.getenv("VERBOSE", "true").lower() == "true"
    MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))
    SEARCH_MAX_RESULTS = int(os.getenv("SEARCH_MAX_RESULTS", "3"))
    SEARCH_DAYS_AHEAD = int(os.getenv("SEARCH_DAYS_AHEAD", "7"))

    # ============= COMMUTE ROUTE CONFIGURATION =============
    ORIGIN_LOCATION = os.getenv("ORIGIN_LOCATION", "New Brunswick, NJ")
    DESTINATION_LOCATION = os.getenv("DESTINATION_LOCATION", "Penn Station, NYC")
    DEFAULT_TRANSPORT_MODE = os.getenv("DEFAULT_TRANSPORT_MODE", "nj_transit")

    # ============= DEFAULT RECIPIENTS =============
    DEFAULT_EMAIL = os.getenv("DEFAULT_EMAIL", "")

    @staticmethod
    def _detect_provider(model: str, api_key: str) -> str:
        """Auto-detect LLM provider from model name prefix."""
        if not model:
            raise ValueError("LLM_MODEL is not set. Please set LLM_MODEL in your .env file.")
        if not api_key:
            raise ValueError("LLM_API_KEY is not set. Please set LLM_API_KEY in your .env file.")
        m = model.lower()
        if m.startswith("claude"):
            return "anthropic"
        if m.startswith(("gpt-", "o1-", "o3-", "o4-")):
            return "openai"
        if m.startswith("gemini"):
            return "google"
        if m.startswith(("mistral", "mixtral", "codestral")):
            return "mistral"
        if m.startswith(("command", "c4ai")):
            return "cohere"
        raise ValueError(
            f"Unknown model '{model}'. Supported prefixes: claude-, gpt-, gemini-, mistral-, command-"
        )

    @staticmethod
    def get_llm():
        """Returns configured LLM instance. Auto-detects provider from LLM_MODEL if set."""
        # --- Option A: Unified path (LLM_MODEL + LLM_API_KEY) ---
        if Config.LLM_MODEL:
            api_key = Config.LLM_API_KEY
            provider = Config._detect_provider(Config.LLM_MODEL, api_key)
            try:
                if provider == "anthropic":
                    return ChatAnthropic(
                        model=Config.LLM_MODEL,
                        temperature=Config.TEMPERATURE,
                        max_tokens=Config.MAX_TOKENS,
                        api_key=api_key,
                    )
                elif provider == "openai":
                    return ChatOpenAI(
                        model=Config.LLM_MODEL,
                        temperature=Config.TEMPERATURE,
                        max_tokens=Config.MAX_TOKENS,
                        api_key=api_key,
                    )
                elif provider == "google":
                    return ChatGoogleGenerativeAI(
                        model=Config.LLM_MODEL,
                        temperature=Config.TEMPERATURE,
                        api_key=api_key,
                    )
                elif provider == "mistral":
                    if not _mistral_available:
                        raise ImportError(
                            "langchain-mistralai is not installed. "
                            "Run: pip install langchain-mistralai"
                        )
                    return ChatMistralAI(
                        model=Config.LLM_MODEL,
                        temperature=Config.TEMPERATURE,
                        mistral_api_key=api_key,
                    )
                elif provider == "cohere":
                    if not _cohere_available:
                        raise ImportError(
                            "langchain-cohere is not installed. "
                            "Run: pip install langchain-cohere"
                        )
                    return ChatCohere(
                        model=Config.LLM_MODEL,
                        temperature=Config.TEMPERATURE,
                        cohere_api_key=api_key,
                    )
            except Exception as e:
                _handle_llm_error(e)

        # --- Option B: Legacy explicit provider path ---
        provider = Config.LLM_PROVIDER.lower()

        if provider == "claude":
            if not Config.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
            try:
                return ChatAnthropic(
                    model=Config.CLAUDE_MODEL,
                    temperature=Config.TEMPERATURE,
                    max_tokens=Config.MAX_TOKENS,
                    api_key=Config.ANTHROPIC_API_KEY,
                )
            except Exception as e:
                _handle_llm_error(e)

        elif provider == "openai":
            if not Config.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY not found in environment variables")
            try:
                return ChatOpenAI(
                    model=Config.OPENAI_MODEL,
                    temperature=Config.TEMPERATURE,
                    max_tokens=Config.MAX_TOKENS,
                    api_key=Config.OPENAI_API_KEY,
                )
            except Exception as e:
                _handle_llm_error(e)

        elif provider == "gemini":
            if not Config.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY not found in environment variables")
            try:
                return ChatGoogleGenerativeAI(
                    model=Config.GEMINI_MODEL,
                    temperature=Config.TEMPERATURE,
                    api_key=Config.GEMINI_API_KEY,
                )
            except Exception as e:
                _handle_llm_error(e)

        elif provider == "mistral":
            if not Config.MISTRAL_API_KEY:
                raise ValueError("MISTRAL_API_KEY not found in environment variables")
            if not _mistral_available:
                raise ImportError("langchain-mistralai is not installed. Run: pip install langchain-mistralai")
            try:
                return ChatMistralAI(
                    model=os.getenv("MISTRAL_MODEL", "mistral-small-latest"),
                    temperature=Config.TEMPERATURE,
                    mistral_api_key=Config.MISTRAL_API_KEY,
                )
            except Exception as e:
                _handle_llm_error(e)

        elif provider == "cohere":
            if not Config.COHERE_API_KEY:
                raise ValueError("COHERE_API_KEY not found in environment variables")
            if not _cohere_available:
                raise ImportError("langchain-cohere is not installed. Run: pip install langchain-cohere")
            try:
                return ChatCohere(
                    model=os.getenv("COHERE_MODEL", "command-r-plus"),
                    temperature=Config.TEMPERATURE,
                    cohere_api_key=Config.COHERE_API_KEY,
                )
            except Exception as e:
                _handle_llm_error(e)

        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    @staticmethod
    def validate():
        """Validate required environment variables. Warns about optional Gmail."""
        # Check LLM keys
        if Config.LLM_MODEL:
            # Unified path — LLM_API_KEY required
            if not Config.LLM_API_KEY:
                raise ValueError("❌ LLM_API_KEY not set in .env file (required when using LLM_MODEL)")
        else:
            # Legacy path
            provider = Config.LLM_PROVIDER.lower()
            if provider == "claude" and not Config.ANTHROPIC_API_KEY:
                raise ValueError("❌ ANTHROPIC_API_KEY not set in .env file")
            if provider == "openai" and not Config.OPENAI_API_KEY:
                raise ValueError("❌ OPENAI_API_KEY not set in .env file")
            if provider == "gemini" and not Config.GEMINI_API_KEY:
                raise ValueError("❌ GEMINI_API_KEY not set in .env file")
            if provider == "mistral" and not Config.MISTRAL_API_KEY:
                raise ValueError("❌ MISTRAL_API_KEY not set in .env file")
            if provider == "cohere" and not Config.COHERE_API_KEY:
                raise ValueError("❌ COHERE_API_KEY not set in .env file")

        if not Config.TAVILY_API_KEY:
            raise ValueError("❌ TAVILY_API_KEY not set in .env file")

        # Gmail is optional — warn but don't raise
        gmail_ok = (
            os.path.exists(Config.GMAIL_TOKEN_PATH) or
            os.path.exists(Config.GMAIL_CREDENTIALS_PATH)
        )
        if not gmail_ok:
            print("ℹ️  Gmail not configured — email reports will be saved to a local HTML file.")
            print("   Run setup_auth.py to enable Gmail sending.\n")

        print("✅ All required API keys are configured")

    @staticmethod
    def print_config():
        """Print current configuration (redacting sensitive keys)"""
        if Config.LLM_MODEL:
            provider = Config._detect_provider(Config.LLM_MODEL, Config.LLM_API_KEY or "?")
            model = Config.LLM_MODEL
        else:
            provider = Config.LLM_PROVIDER.lower()
            if provider == "claude":
                model = Config.CLAUDE_MODEL
            elif provider == "openai":
                model = Config.OPENAI_MODEL
            elif provider == "gemini":
                model = Config.GEMINI_MODEL
            else:
                model = os.getenv(f"{provider.upper()}_MODEL", "Unknown")

        print("\n" + "=" * 60)
        print("🔧 TRIP AGENT CONFIGURATION")
        print("=" * 60)
        print(f"LLM Provider: {provider}")
        print(f"Model: {model}")
        print(f"Temperature: {Config.TEMPERATURE}")
        print(f"Max Tokens: {Config.MAX_TOKENS}")
        print(f"Max Iterations: {Config.MAX_ITERATIONS}")
        print(f"Verbose: {Config.VERBOSE}")
        print("=" * 60 + "\n")
