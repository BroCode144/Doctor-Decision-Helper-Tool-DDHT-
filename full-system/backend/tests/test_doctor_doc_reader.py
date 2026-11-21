"""The doctor-document reader: certificate scans go to Groq, photo IDs never leave the server."""
import fitz

from app.core.config import get_settings
from app.modules.doctors import doctor_documents as dd
def _png() -> bytes:
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 20), 0)
    pix.clear_with(255)
    return pix.tobytes("png")


class _Resp:
    status_code = 200
    headers: dict = {}

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "Maharashtra Medical Council\nCertificate of Registration"}}]}


def _reader_on(monkeypatch, calls):
    s = get_settings()
    monkeypatch.setattr(s, "doctor_doc_reader", "qwen/qwen3.8-27b")
    monkeypatch.setattr(s, "doctor_doc_groq_api_key", "test-key")
    monkeypatch.setattr(dd.httpx, "post", lambda url, **kw: calls.append((url, kw)) or _Resp())


def test_certificate_photo_is_read_by_groq(monkeypatch):
    calls = []
    _reader_on(monkeypatch, calls)
    text, method = dd.read(_png(), "image/png", "REGISTRATION")
    assert method == dd.READER_LABEL and "Medical Council" in text
    assert len(calls) == 1 and calls[0][0] == dd.GROQ_URL
    content = calls[0][1]["json"]["messages"][0]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_photo_id_is_never_sent(monkeypatch):
    calls = []
    _reader_on(monkeypatch, calls)
    for mime, data in (("image/png", _png()), ("application/pdf", _blank_pdf())):
        text, method = dd.read(data, mime, "PHOTO_ID")
        assert text is None and "private" in method
    assert calls == []


def test_reader_off_without_key(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "doctor_doc_reader", "qwen/qwen3.8-27b")
    monkeypatch.setattr(s, "doctor_doc_groq_api_key", None)
    monkeypatch.setattr(s, "groq_api_key", "main-chat-key")  # the chat key is never used as a fallback
    monkeypatch.setattr(dd.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    assert dd.read(_png(), "image/png", "DEGREE") == (None, "not read")


def test_large_photo_is_shrunk():
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 3000, 3000), 0)
    pix.clear_with(200)
    big = pix.tobytes("png")
    out, mime = dd._shrink(big + b"\0" * max(0, dd.MAX_IMAGE_BYTES + 1 - len(big)))
    assert len(out) <= dd.MAX_IMAGE_BYTES and mime == "image/jpeg"


def _blank_pdf() -> bytes:
    d = fitz.open()
    d.new_page()
    return d.tobytes()


def test_waits_and_retries_when_rate_limited(monkeypatch):
    class _Limited(_Resp):
        status_code = 429
        headers = {"retry-after": "2"}

    class _Ok(_Resp):
        status_code = 200
        headers = {}

    replies, slept = [_Limited(), _Ok()], []
    s = get_settings()
    monkeypatch.setattr(s, "doctor_doc_reader", "qwen/qwen3.8-27b")
    monkeypatch.setattr(s, "doctor_doc_groq_api_key", "test-key")
    monkeypatch.setattr(dd.httpx, "post", lambda *a, **k: replies.pop(0))
    monkeypatch.setattr(dd.time, "sleep", slept.append)
    text, _ = dd.read(_png(), "image/png", "REGISTRATION")
    assert "Medical Council" in text and slept == [2.0]
