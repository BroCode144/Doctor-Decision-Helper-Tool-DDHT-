import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.db.session import engine
from app.modules.admin.router import router as admin_router
from app.modules.ai.router import router as ai_router
from app.modules.appointments.router import router as appointments_router
from app.modules.auth.router import router as auth_router
from app.modules.booking.chat_router import router as booking_chat_router
from app.modules.booking.router import router as booking_router
from app.modules.doctors.router import router as doctors_router
from app.modules.records.documents_router import router as documents_router
from app.modules.records.router import router as records_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
register_exception_handlers(app)

# One router per feature module (app/modules/<feature>/). Decision support is optional, below.
for r in (auth_router, records_router, documents_router, ai_router, appointments_router, admin_router, booking_router,
          doctors_router, booking_chat_router):
    app.include_router(r)

# Optional module: switch off with DECISION_SUPPORT_ENABLED=false, or delete app/modules/decision_support (see README).
if settings.decision_support_enabled:
    from app.modules.decision_support.router import router as decision_support_router

    app.include_router(decision_support_router)


@app.get("/health", tags=["meta"])
def health():
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "unavailable",
        "ai_configured": settings.llm_configured,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model_name,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": {"huggingface": settings.hf_embedding_model, "ollama": settings.ollama_embedding_model}.get(
            settings.embedding_provider, "local-hashing"),
    }
