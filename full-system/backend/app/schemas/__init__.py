from datetime import date, datetime, time

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models import RecordType


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\s*\d{6}\s*$")


class ResendCodeRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\s*\d{6}\s*$")
    password: str = Field(min_length=8, max_length=200)

    @field_validator("password")
    @classmethod
    def _complex(cls, v: str) -> str:
        if not any(c.isdigit() for c in v) or not any(c.isalpha() for c in v):
            raise ValueError("Password must contain letters and numbers.")
        return v


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    full_name: str = Field(min_length=2, max_length=200)
    role: str = Field(pattern="^(PATIENT|DOCTOR)$")
    # patient
    date_of_birth: date | None = None
    gender: str | None = Field(None, max_length=32)
    phone: str | None = Field(None, max_length=40)
    # doctor
    specialization: str | None = Field(None, max_length=120)
    license_number: str | None = Field(None, max_length=64)
    hospital_id: str | None = None

    @field_validator("password")
    @classmethod
    def _complex(cls, v: str) -> str:
        if not any(c.isdigit() for c in v) or not any(c.isalpha() for c in v):
            raise ValueError("Password must contain letters and numbers.")
        return v


class ProfileUpdate(BaseModel):
    phone: str | None = Field(None, max_length=40)
    address: str | None = Field(None, max_length=300)
    emergency_contact: str | None = Field(None, max_length=200)
    blood_group: str | None = Field(None, max_length=8)
    gender: str | None = Field(None, max_length=32)
    date_of_birth: date | None = None


class RecordCreate(BaseModel):
    record_type: RecordType
    title: str = Field(min_length=2, max_length=250)
    record_date: date
    description: str | None = Field(None, max_length=5000)


class RecordStatusUpdate(BaseModel):
    status: str = Field(pattern="^(ACTIVE|RESTRICTED|ARCHIVED)$")
    reason: str | None = Field(None, max_length=500)


class ConsentRequestCreate(BaseModel):
    reason: str | None = Field(None, max_length=300)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class CompareRequest(BaseModel):
    document_a_id: str = Field(min_length=1, max_length=32)
    document_b_id: str = Field(min_length=1, max_length=32)


class VerifyDoctorRequest(BaseModel):
    status: str = Field("VERIFIED", pattern="^(VERIFIED|REJECTED|PENDING)$")
    notes: str | None = Field(None, max_length=1000)


class UserStatusUpdate(BaseModel):
    is_active: bool


class VisitCreate(BaseModel):
    doctor_id: str
    patient_id: str
    visit_date: date


# --- Appointments -----------------------------------------------------------
class AppointmentCreate(BaseModel):
    doctor_id: str = Field(min_length=1, max_length=32)
    start_at: datetime  # must include a time zone; must match one of the doctor's free slots
    reason: str = Field(min_length=2, max_length=500)  # the patient's symptoms in their own words (required)
    timezone: str | None = Field(None, max_length=64)  # patient's IANA time zone, for display
    share_records: bool = False
    # Required booking questions (app.modules.booking.questionnaire): duration, severity, red_flags, smoking, ...
    answers: dict
    intake: dict | None = None  # {"form": {...}} from the intake chat (app.modules.booking.intake_schema); optional


class AppointmentUpdate(BaseModel):
    """Doctor confirms (status=CONFIRMED) or either participant moves it (start_at=...)."""
    status: str | None = Field(None, pattern="^CONFIRMED$")
    start_at: datetime | None = None


class AppointmentCancel(BaseModel):
    reason: str | None = Field(None, max_length=500)


class WeeklyHours(BaseModel):
    weekday: int = Field(ge=0, le=6)  # 0 = Monday
    start_time: time
    end_time: time
    slot_minutes: int = Field(ge=5, le=180)
    timezone: str = Field(min_length=1, max_length=64)


class AvailabilityUpdate(BaseModel):
    weekly_hours: list[WeeklyHours] = Field(max_length=50)


class TimeOffCreate(BaseModel):
    start_date: date
    end_date: date
    reason: str | None = Field(None, max_length=200)



class CheckInRequest(BaseModel):
    """Reception at check-in. Everything optional, but at least one of symptoms / red flags / a vital is required."""
    symptoms: str | None = Field(None, max_length=1000)
    duration: str | None = Field(None, max_length=100)
    severity: str | None = Field(None, pattern="^(mild|moderate|severe)$")
    red_flags: list[str] = Field(default_factory=list, max_length=8)
    systolic_bp: int | None = Field(None, ge=50, le=260)
    diastolic_bp: int | None = Field(None, ge=30, le=160)
    pulse: int | None = Field(None, ge=20, le=250)
    temperature_c: float | None = Field(None, ge=30, le=45)
    spo2: int | None = Field(None, ge=50, le=100)
    weight_kg: float | None = Field(None, ge=1, le=350)
    height_cm: float | None = Field(None, ge=30, le=250)


class SymptomsAdd(BaseModel):
    text: str = Field(min_length=2, max_length=1000)
    duration: str | None = Field(None, max_length=100)
    appointment_id: str | None = Field(None, max_length=32)


class HistoryItemCreate(BaseModel):
    kind: str = Field(pattern="^(ALLERGY|SURGERY|CONDITION|FAMILY|MEDICATION|NO_KNOWN_ALLERGIES)$")
    name: str | None = Field(None, max_length=200)
    detail: str | None = Field(None, max_length=300)


class LocalDiseaseCreate(BaseModel):
    city: str = Field(min_length=2, max_length=100)
    disease: str = Field(min_length=2, max_length=120)
    start_month: int = Field(ge=1, le=12)
    end_month: int = Field(ge=1, le=12)
    level: str = Field("HIGH", pattern="^(HIGH|MEDIUM)$")
    source: str = Field(min_length=2, max_length=200)
    note: str | None = Field(None, max_length=300)
