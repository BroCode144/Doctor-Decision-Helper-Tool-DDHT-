"""Intake chat endpoints (patients only). The schema, the patient's pre-filled record, and one chat turn.
Nothing is saved here: the intake is saved with the booking (POST /appointments, field `intake`)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_llm_factory, require_roles
from app.db.session import get_db
from app.models import Role, User
from app.modules.booking import intake_engine
from app.modules.booking import intake_schema
router = APIRouter(tags=["intake chat"])
patient_only = require_roles(Role.PATIENT)


class IntakeTurn(BaseModel):
    state: dict | None = None  # as returned by the last turn (form, messages, ...); None to start
    message: str | None = Field(None, max_length=1000)  # what the patient typed or tapped (quick replies are text)


@router.get("/intake/schema")
def schema(_: User = Depends(patient_only)):
    return intake_schema.public_schema()


@router.get("/intake/context")
def context(user: User = Depends(patient_only), db: Session = Depends(get_db)):
    """The form pre-filled from the patient's records, and what the chat knows about them."""
    return intake_engine.context_payload(db, user)


@router.post("/intake/chat")
def chat(body: IntakeTurn, user: User = Depends(patient_only), db: Session = Depends(get_db),
         llm_factory=Depends(get_llm_factory)):
    """One turn. Returns assistant_message, quick_replies, silent_form_updates (fields filled this turn),
    extracted_clinical_codes (for the doctor), red_flag_triggered, and the conversation state to send back."""
    return intake_engine.turn(db, user, body.state, body.message, llm_factory)
