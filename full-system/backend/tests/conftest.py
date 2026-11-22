"""Test fixtures.

Tests run against a real PostgreSQL database (`ddht_test`), a real Chroma
store and real PyMuPDF processing in a temp dir. Embeddings use the local
hashing provider (no network). The LLM is replaced by a recording fake so the
tests can assert exactly what reached the AI context; the real Llama client
is exercised separately in test_llm_live.py when HF_TOKEN is set.
"""

import getpass
import os
import re
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="ddht-test-"))
os.environ.update(
    DATABASE_URL=os.environ.get("TEST_DATABASE_URL", f"postgresql+psycopg://{getpass.getuser()}@localhost:5432/ddht_test"),
    JWT_SECRET="test-secret-" + "x" * 40,
    EMBEDDING_PROVIDER="hash",
    UPLOAD_DIR=str(_tmp / "uploads"),
    CHROMA_DIR=str(_tmp / "chroma"),
    CHROMA_COLLECTION="ddht_test_docs",
    BCRYPT_ROUNDS="4",
    MEDICAL_CHECK_READER="",
    DOCTOR_DOC_READER="",  # doctor-application photos are not read in tests (PDF text still is)
    OUTBOX_DIR=str(_tmp / "outbox"),
    SMTP_USER="",  # tests never send real email (codes are captured below)
    SMTP_PASSWORD="",  # tests never call the local reading model (photos are then accepted as "not checked")
    HF_TOKEN_TEST_BACKUP=os.environ.get("HF_TOKEN", ""),
    HF_TOKEN="",
    # Never let tests use the real keys from backend/.env.
    LLM_PROVIDER="huggingface",
    LLM_FALLBACKS="",
    GROQ_API_KEY="",
    CEREBRAS_API_KEY="",
    DEEPSEEK_API_KEY="",
    OPENROUTER_API_KEY="",
    GEMINI_API_KEY="",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.modules.ai import vector_store  # noqa: E402
from app.core.deps import get_llm_factory  # noqa: E402
from app.db.init_db import make_pdf, seed  # noqa: E402
from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


class FakeLLM:
    """Records prompts. Answers by citing the first two sources in the context,
    or with the insufficient-information sentence when told to."""

    model = "fake-llm-for-tests"

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.force_insufficient = False

    def complete(self, system: str, user: str, max_tokens: int = 900) -> str:
        self.calls.append((system, user))
        if self.force_insufficient:
            return "The available patient records do not contain sufficient information to answer this question."
        refs = re.findall(r"\[(S\d+)\]", user)[:2]
        return "DOCUMENTED: " + " ".join(f"fact [{r}]" for r in refs)

    @property
    def all_prompts(self) -> str:
        return "\n".join(u for _, u in self.calls)


@pytest.fixture()
def fake_llm():
    return FakeLLM()


@pytest.fixture()
def client(fake_llm):
    import shutil

    Base.metadata.drop_all(engine)
    shutil.rmtree(_tmp / "uploads", ignore_errors=True)
    vector_store.reset_collection()
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    app.dependency_overrides[get_llm_factory] = lambda: (lambda: fake_llm)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


SENT_CODES: dict[str, str] = {}  # email -> the last sign-up code "sent"


@pytest.fixture(autouse=True)
def _capture_email_codes(monkeypatch):
    from app.modules.auth import email_verification
    SENT_CODES.clear()

    def fake_send(to, name, code, purpose="verify"):
        SENT_CODES[to] = code
        return True

    monkeypatch.setattr(email_verification, "_send", fake_send)


def register(client, body):
    """Sign up, and for a patient type the emailed code, like a real user."""
    r = client.post("/auth/register", json=body)
    if r.status_code == 201 and r.json().get("needs_verification"):
        v = client.post("/auth/verify-email", json={"email": body["email"], "code": SENT_CODES[body["email"].lower()]})
        assert v.status_code == 200, v.text
    return r


def login(client, email, password):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def doctor(client):  # D001 Dr. Raj Mehta
    return login(client, "doctor@ddht.demo", "doctor123")


@pytest.fixture()
def doctor2(client):  # D002 Dr. Anjali Shah
    return login(client, "anjali@ddht.demo", "doctor123")


@pytest.fixture()
def patient(client):  # P001 Rahul Sharma
    return login(client, "patient@ddht.demo", "patient123")


@pytest.fixture()
def patient2(client):  # P002 Priya Shah
    return login(client, "priya@ddht.demo", "patient123")


@pytest.fixture()
def patient3(client):  # P003 Aman Patel
    return login(client, "aman@ddht.demo", "patient123")


@pytest.fixture()
def admin(client):  # A001 (has can_manage_patient_documents)
    return login(client, "admin@ddht.demo", "admin123")


@pytest.fixture()
def admin_limited(client):  # A002 (no patient-document permission)
    return login(client, "records.admin@ddht.demo", "admin123")


def pdf_bytes(lines=("Test report", "Hemoglobin: 12.0 g/dL")):
    return make_pdf("Uploaded Test Report", list(lines))


def upload(client, headers, *, data=None, filename="report.pdf", mime="application/pdf", **fields):
    form = {"document_type": "LAB_REPORT", "document_date": "2026-09-01", "title": "Test upload"}
    form.update({k: v for k, v in fields.items() if v is not None})
    return client.post(
        "/documents/upload",
        headers=headers,
        data=form,
        files={"file": (filename, data if data is not None else pdf_bytes(), mime)},
    )


def logs(client, admin_headers, **params):
    r = client.get("/access-logs", headers=admin_headers, params=params)
    assert r.status_code == 200
    return r.json()
