"""Application settings.

All secrets (JWT_SECRET, HF_TOKEN, DATABASE_URL credentials) come from the
environment / backend `.env` file. Nothing secret is hardcoded here.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
LLM_PROVIDERS = ("ollama", "huggingface", "groq", "cerebras", "deepseek", "openrouter", "gemini")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Core -------------------------------------------------------------
    app_name: str = "DDHT Full System API"
    environment: str = "development"
    database_url: str = Field(..., alias="DATABASE_URL")

    # --- Auth -------------------------------------------------------------
    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(120, alias="JWT_EXPIRE_MINUTES")
    bcrypt_rounds: int = Field(12, ge=4, le=16, alias="BCRYPT_ROUNDS")

    # --- Email (sign-up codes). Gmail: SMTP_USER = the Gmail address, SMTP_PASSWORD = a Google "app password"
    # (Google account > Security > 2-Step Verification > App passwords). Blank = no email is sent; the code is
    # written to the backend log instead (local development only).
    smtp_host: str = Field("smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(587, alias="SMTP_PORT")
    smtp_user: str = Field("", alias="SMTP_USER")
    smtp_password: str = Field("", alias="SMTP_PASSWORD")
    smtp_from_name: str = Field("DDHT", alias="SMTP_FROM_NAME")

    # --- Doctor applications (app/modules/doctors/doctor_onboarding.py) ------------------------------------------
    # Groq vision model that READS photos / scans of doctors' certificates (photo IDs are never sent).
    # It uses its OWN key from a separate Groq account, never GROQ_API_KEY, so it doesn't share the chat's rate limit.
    # Empty model or no key = not read (the admin checks by eye).
    doctor_doc_reader: str = Field("qwen/qwen3.8-27b", alias="DOCTOR_DOC_READER")
    doctor_doc_groq_api_key: str | None = Field(None, alias="DOCTOR_DOC_GROQ_API_KEY")
    # Where emailed links point if the request has no Origin header (e.g. http://localhost:5174 or the tunnel URL).
    public_app_url: str = Field("http://localhost:5174", alias="PUBLIC_APP_URL")
    # When Gmail is not set up, emails are saved here as .txt files so they can still be shown in a demo.
    outbox_dir: Path = Field(BACKEND_DIR / "storage" / "outbox", alias="OUTBOX_DIR")

    # --- CORS -------------------------------------------------------------
    cors_origins: str = Field(
        "http://localhost:5174,http://127.0.0.1:5174", alias="CORS_ORIGINS"
    )

    # --- Storage ----------------------------------------------------------
    storage_backend: str = Field("local", alias="STORAGE_BACKEND")
    upload_dir: Path = Field(BACKEND_DIR / "storage" / "uploads", alias="UPLOAD_DIR")
    max_upload_mb: int = Field(10, alias="MAX_UPLOAD_MB")
    # Uploaders may delete their own upload (e.g. wrong file) within this many days.
    upload_undo_days: int = Field(7, ge=0, le=365, alias="UPLOAD_UNDO_DAYS")

    # --- Appointments -----------------------------------------------------
    booking_window_days: int = Field(30, ge=1, le=365, alias="BOOKING_WINDOW_DAYS")

    # --- Decision support (optional module: scores, trends, medication safety, symptom match) -----
    decision_support_enabled: bool = Field(True, alias="DECISION_SUPPORT_ENABLED")

    # --- AI / RAG ---------------------------------------------------------
    # Chat model provider: ollama | huggingface | groq | cerebras | deepseek | openrouter | gemini
    # Default: GPT-OSS 120B on Groq (free tier; most accurate in our tests), with MedGemma on this computer
    # (Ollama) as the automatic backup when Groq is busy, out of quota or offline.
    llm_provider: str = Field("groq", alias="LLM_PROVIDER")
    # Optional comma-separated backups tried when the main one is rate-limited, out of
    # credit or down. Each entry is "provider" or "provider:model",
    # e.g. "groq:qwen/qwen3.8-27b,openrouter".
    # Tested backups in order (12 Nov 2026): GPT-OSS 20B (its own Groq limit), Gemini 2.5 Flash (a different
    # company), then MedGemma on this computer (offline). Entries without a key are skipped.
    llm_fallbacks: str = Field("groq:openai/gpt-oss-20b,gemini,ollama", alias="LLM_FALLBACKS")
    # Only sent to reasoning models (gpt-oss): "low" keeps answers fast and within max_tokens.
    llm_reasoning_effort: str = Field("low", alias="LLM_REASONING_EFFORT")
    # On a free-tier per-minute limit, wait up to this many seconds and retry once.
    llm_max_rate_limit_wait: float = Field(30, alias="LLM_MAX_RATE_LIMIT_WAIT")
    # Ollama serves an OpenAI-compatible API on this computer; no key is needed.
    ollama_model: str = Field("medgemma1.5:4b", alias="OLLAMA_MODEL")
    ollama_base_url: str = Field("http://localhost:11434/v1", alias="OLLAMA_BASE_URL")
    # Context window per request. Ollama's default (4096 tokens) silently cut off longer prompts.
    # Local vision model that READS the text of photos/scans of patient uploads for the medical-content check
    # (app/modules/records/medical_check.py). Empty = skip reading (such files are accepted and marked "not checked").
    medical_check_reader: str = Field("medgemma1.5:4b", alias="MEDICAL_CHECK_READER")
    ollama_num_ctx: int = Field(16384, ge=2048, le=131072, alias="OLLAMA_NUM_CTX")
    # Same all-MiniLM-L6-v2 model as HF_EMBEDDING_MODEL, served by Ollama (ollama pull all-minilm).
    ollama_embedding_model: str = Field("all-minilm", alias="OLLAMA_EMBEDDING_MODEL")
    groq_api_key: str | None = Field(None, alias="GROQ_API_KEY")
    groq_model: str = Field("openai/gpt-oss-120b", alias="GROQ_MODEL")
    cerebras_api_key: str | None = Field(None, alias="CEREBRAS_API_KEY")
    cerebras_model: str = Field("gpt-oss-120b", alias="CEREBRAS_MODEL")
    deepseek_api_key: str | None = Field(None, alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field("deepseek-chat", alias="DEEPSEEK_MODEL")
    openrouter_api_key: str | None = Field(None, alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field("", alias="OPENROUTER_MODEL")
    gemini_api_key: str | None = Field(None, alias="GEMINI_API_KEY")
    # Stable model; "gemini-flash-latest" (newest Flash) was often overloaded (HTTP 503) on the free tier.
    gemini_model: str = Field("gemini-2.5-flash", alias="GEMINI_MODEL")
    hf_token: str | None = Field(None, alias="HF_TOKEN")
    # Hosted MedGemma 27B: needs the model's terms accepted, the "featherless-ai" provider enabled
    # in the Hugging Face settings, and paid credit after the small monthly allowance.
    hf_model: str = Field("google/medgemma-27b-text-it", alias="HF_MODEL")
    hf_embedding_model: str = Field(
        "sentence-transformers/all-MiniLM-L6-v2", alias="HF_EMBEDDING_MODEL"
    )
    # "ollama"      -> local all-MiniLM-L6-v2 through Ollama (default, free)
    # "huggingface" -> HF Inference API embeddings (needs HF_TOKEN and credit)
    # "hash"        -> deterministic local lexical (feature-hashing) embeddings,
    #                  used for offline development and the test-suite.
    embedding_provider: str = Field("ollama", alias="EMBEDDING_PROVIDER")
    chroma_dir: Path = Field(BACKEND_DIR / "storage" / "chroma", alias="CHROMA_DIR")
    chroma_collection: str = Field("ddht_patient_documents", alias="CHROMA_COLLECTION")
    ai_timeout_seconds: int = Field(60, alias="AI_TIMEOUT_SECONDS")
    rag_top_k: int = Field(6, alias="RAG_TOP_K")
    # Cosine distance cut-off for RAG hits (0 = identical, 1 = unrelated).
    rag_max_distance: float = Field(1.0, alias="RAG_MAX_DISTANCE")

    @field_validator("jwt_secret")
    @classmethod
    def _strong_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters long")
        return v

    @field_validator("hf_token", "groq_api_key", "doctor_doc_groq_api_key", "cerebras_api_key", "deepseek_api_key", "openrouter_api_key", "gemini_api_key")
    @classmethod
    def _blank_token_is_none(cls, v: str | None) -> str | None:
        if v is None or not v.strip() or v.strip().startswith("your_"):
            return None
        return v.strip()

    @field_validator("llm_provider")
    @classmethod
    def _known_provider(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in LLM_PROVIDERS:
            raise ValueError(f"LLM_PROVIDER must be one of: {', '.join(LLM_PROVIDERS)}")
        return v

    def llm_key(self, provider: str) -> str | None:
        if provider == "ollama":
            return "ollama"  # local server: any non-empty key is accepted
        return self.hf_token if provider == "huggingface" else getattr(self, f"{provider}_api_key")

    def llm_model_for(self, provider: str) -> str:
        return self.hf_model if provider == "huggingface" else getattr(self, f"{provider}_model")

    @property
    def llm_chain(self) -> list[tuple[str, str]]:
        """[(provider, model), ...]: the main provider first, then valid, de-duplicated fallbacks."""
        chain = [(self.llm_provider, self.llm_model_name)]
        for entry in self.llm_fallbacks.split(","):
            provider, _, model = entry.strip().partition(":")
            provider = provider.strip().lower()
            if provider not in LLM_PROVIDERS:
                continue
            item = (provider, model.strip() or self.llm_model_for(provider))
            if item[1] and item not in chain:
                chain.append(item)
        return chain

    @property
    def llm_fallback_list(self) -> list[str]:
        return [f"{p}:{m}" for p, m in self.llm_chain[1:]]

    @property
    def llm_configured(self) -> bool:
        return any(self.llm_key(p) and m for p, m in self.llm_chain)

    @property
    def llm_model_name(self) -> str:
        return self.llm_model_for(self.llm_provider)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
