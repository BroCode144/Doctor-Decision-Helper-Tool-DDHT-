import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { useToast } from "../../context/contexts";
import { api } from "../../lib/api";
import { fmtSlot, viewerTimeZone } from "../../lib/time";
import { useApi } from "../../hooks/useApi";
import { Button, ErrorState, Loading, PageHeader } from "../../components/ui";
import BookingChat from "../../features/booking/BookingChat";

/**
 * Booking step 3: one short conversation (BookingChat) instead of a long form. Its answers go to the doctor with the
 * appointment and fill in the risk calculations (smoking, diabetes, BP medicine, chest-pain type), so the doctor only
 * has to ask for what a patient cannot know (lab values, ECG, ...).
 */
export default function BookingDetails() {
  const { state } = useLocation();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const q = useApi(() => api.get("/booking/questions"), []);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  if (!state?.doctor || !state?.slot) return <Navigate to="/patient/appointments/book" replace />;
  const { doctor, slot } = state;
  const pickAnother = () => navigate("/patient/appointments/book", { state: { doctorId: doctor.id } });

  const submit = async ({ reason, answers, intake, share }) => {
    setBusy(true);
    setErr(null);
    try {
      const a = await api.post("/appointments", { doctor_id: doctor.id, start_at: slot.start_at, reason,
        timezone: viewerTimeZone(), share_records: share, answers, intake });
      showToast("Appointment requested. You'll be notified when the doctor confirms.", "success");
      navigate(`/patient/appointments?focus=${a.id}`);
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <button type="button" onClick={pickAnother}
        className="inline-flex items-center gap-1 text-sm font-semibold text-ink-500 hover:text-ink-800">
        <ArrowLeft size={16} /> Change the time
      </button>
      <PageHeader title="Tell the doctor about your problem" subtitle={`Step 3 of 3 · ${doctor.name} · ${fmtSlot(slot.start_at, slot.end_at)}`} />
      {q.loading && <Loading />}
      <ErrorState error={q.error} onRetry={q.reload} />
      {q.data && (
        <BookingChat questions={q.data} doctorName={doctor.name} onSubmit={submit} busy={busy} error={err}
          errorAction={err?.code === "SLOT_UNAVAILABLE" && <Button variant="secondary" onClick={pickAnother}>Pick another time</Button>} />
      )}
    </div>
  );
}
