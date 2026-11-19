import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Bot, CalendarCheck, CheckCircle2, LocateFixed, RotateCcw, Send, Upload } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { Button, Card, ErrorState, inputCls } from "../../components/ui";

const CHAT_GUESS = 8; // chat questions expected before the server says how many are left (it asks a limited number)

// "None of these" in the warning-sign list answers these chat warning signs too, so the chat doesn't ask them again.
const COVERED_BY_NONE = ["severe_breathlessness", "confusion_fainting", "uncontrolled_bleeding", "seizure_or_stiff_neck"];

const applies = (q, ans) =>
  (!q.only_if || Object.entries(q.only_if).every(([k, v]) => ans[k] === v)) &&
  (!q.skip_if || !Object.entries(q.skip_if).every(([k, v]) => ans[k] === v));

/** Distance in km between two points (haversine). */
function km(aLat, aLon, bLat, bLon) {
  const r = (d) => (d * Math.PI) / 180;
  const h = Math.sin(r(bLat - aLat) / 2) ** 2 + Math.cos(r(aLat)) * Math.cos(r(bLat)) * Math.sin(r(bLon - aLon) / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

function Bubble({ role, children }) {
  const me = role === "patient";
  return (
    <div className={`flex ${me ? "justify-end" : "justify-start"}`}>
      {!me && <span className="mr-2 mt-1 flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-700"><Bot size={15} /></span>}
      <p className={`max-w-[85%] whitespace-pre-line rounded-2xl px-3.5 py-2 text-sm ${me ? "rounded-br-sm bg-brand-600 text-white" : "rounded-bl-sm bg-ink-50 text-ink-800"}`}>{children}</p>
    </div>
  );
}

function Chip({ children, onClick, on = false }) {
  return (
    <button type="button" onClick={onClick}
      className={`rounded-xl border px-3 py-1.5 text-sm transition ${on ? "border-brand-500 bg-brand-600 font-semibold text-white" : "border-ink-200 bg-white text-ink-700 hover:border-brand-400 hover:bg-brand-50"}`}>
      {children}
    </button>
  );
}

/** The warning-sign checklist, asked first: an emergency shouldn't wait behind other questions. */
function FlagsInput({ flags, onDone }) {
  const [picked, setPicked] = useState([]);
  const toggle = (c) => setPicked((p) => (p.includes(c) ? p.filter((x) => x !== c) : [...p, c]));
  return (
    <div className="space-y-2">
      <div className="grid gap-1.5 sm:grid-cols-2">
        {flags.map((f) => (
          <label key={f.code} className="flex cursor-pointer items-start gap-2 rounded-lg border border-ink-100 bg-white p-2 text-sm text-ink-800">
            <input type="checkbox" className="mt-0.5" checked={picked.includes(f.code)} onChange={() => toggle(f.code)} />
            {f.label}
          </label>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="secondary" icon={CheckCircle2} disabled={picked.length > 0} onClick={() => onDone([])}>None of these</Button>
        <Button type="button" disabled={!picked.length} onClick={() => onDone(picked)}>I have {picked.length === 1 ? "this" : "these"}</Button>
      </div>
    </div>
  );
}

const ALWAYS_ASK = ["city", "travel", "travel_city"];

/** A city question: a list, plus "Use my location" (the nearest city is found HERE; the position is never sent). */
function CityInput({ q, maxKm, gps, known, onDone }) {
  const [value, setValue] = useState(known || "");
  const [note, setNote] = useState(known ? `We have ${known} from before. Tap OK if that's still right, or choose another.` : null);
  const [locating, setLocating] = useState(false);
  const locate = () => {
    if (!navigator.geolocation || !window.isSecureContext) {
      setNote("Location isn't available on this link. Please choose from the list.");
      return;
    }
    setLocating(true);
    setNote(null);
    navigator.geolocation.getCurrentPosition((pos) => {
      setLocating(false);
      const { latitude, longitude } = pos.coords;
      const best = q.options.filter((o) => o.lat !== undefined)
        .map((o) => ({ o, d: km(latitude, longitude, o.lat, o.lon) }))
        .sort((a, b) => a.d - b.d)[0];
      if (best && best.d <= maxKm) {
        setValue(best.o.value);
        setNote(`Nearest listed city: ${best.o.value} (about ${Math.round(best.d)} km). Your exact location was not saved or sent.`);
      } else {
        setNote(`No listed city within ${maxKm} km of you. Please choose the nearest one, or 'Other'.`);
      }
    }, (e) => {
      setLocating(false);
      setNote(e.code === 1 ? "Location permission was not given. That's fine: please choose from the list." : "Couldn't get your location. Please choose from the list.");
    }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 });
  };
  return (
    <div>
      <div className="flex flex-wrap gap-2">
        <select aria-label={q.label} className={`${inputCls} max-w-xs`} value={value} onChange={(e) => setValue(e.target.value)}>
          <option value="">Choose a city…</option>
          {q.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        {gps && <Button type="button" variant="secondary" icon={LocateFixed} loading={locating} onClick={locate}>Use my location</Button>}
        <Button type="button" disabled={!value} onClick={() => onDone(value, q.options.find((o) => o.value === value)?.label)}>OK</Button>
      </div>
      {note && <p className="mt-1.5 text-xs text-ink-500">{note}</p>}
    </div>
  );
}

/**
 * Booking step 3 as one conversation:
 *   1. the patient describes the problem in their own words;
 *   2. warning signs (a checklist, straight after, so an emergency is caught at once);
 *   3. the intake chat: follow-up questions that fit what the patient said (the server fills the doctor's intake
 *      record behind the scenes and asks a limited number of questions);
 *   4. the booking questions the chat didn't already answer, one at a time with tap-to-answer buttons;
 *   5. checkboxes and "Request appointment".
 * The assistant never diagnoses or advises.
 */
export default function BookingChat({ questions, doctorName, onSubmit, busy, error, errorAction }) {
  const [log, setLog] = useState([]); // what the patient sees: {role, text}
  const [stage, setStep] = useState("first"); // first -> flags -> chat -> quick (-> final once nothing is left)
  const [flags, setFlags] = useState(null);
  const [intake, setIntake] = useState(null); // the chat's server state
  const [view, setView] = useState(null); // the last chat turn
  const [ans, setAns] = useState({}); // booking answers
  const [fromChat, setFromChat] = useState({}); // booking answers the chat filled
  const [reason, setReason] = useState("");
  const [text, setText] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [agree, setAgree] = useState(false);
  const [share, setShare] = useState(false);
  const [tried, setTried] = useState(false);
  const box = useRef(null);

  const say = (role, t) => setLog((l) => [...l, { role, text: t }]);
  const all = { ...fromChat, ...ans };
  // Where the patient is matters for this illness, so the location questions are always shown (a city we already
  // know is pre-selected for a one-tap confirm); other questions the chat already answered are skipped.
  const pending = questions.questions.filter((x) => applies(x, all) && (ALWAYS_ASK.includes(x.id) ? ans[x.id] === undefined : all[x.id] === undefined));
  const step = stage === "quick" && !pending.length ? "final" : stage;
  const current = step === "quick" ? pending[0] : null;
  const urgent = flags?.length > 0 || view?.red_flag_triggered;

  // The greeting comes from the server, which also loads what the patient's records already say.
  const begin = async () => {
    setChatBusy(true);
    setErr(null);
    try {
      const out = await api.post("/intake/chat", { state: null, message: null });
      setIntake(out.state);
      setView(out);
      setFromChat(out.booking_answers || {});
      setLog([{ role: "assistant", text: `${out.assistant_message}\n\nTell me in your own words. After that I'll ask a few short questions so ${doctorName} is ready for your visit.` }]);
    } catch (e) {
      setErr(e.message);
    } finally {
      setChatBusy(false);
    }
  };
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    begin(); // eslint-disable-line react-hooks/exhaustive-deps
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { box.current?.scrollTo({ top: box.current.scrollHeight, behavior: "smooth" }); }, [log.length, chatBusy, step]);

  const start = () => {
    setLog([]);
    setStep("first"); setFlags(null); setIntake(null); setView(null); setAns({}); setFromChat({}); setReason("");
    setErr(null); setAgree(false); setImprove(false); setTried(false);
    begin();
  };

  // When the chat ends (or on an urgent answer), go on to whatever booking question is still open.
  const finishChat = (lastText) => {
    if (lastText) say("assistant", lastText);
    setStep("quick");
  };

  const URGENT = "Thank you. Because of the warning sign you ticked, please don't wait for this appointment: call 108 or go to the "
    + "nearest emergency department. A few quick questions so your doctor is ready.";
  const chat = async (message, state, urgentNow = false) => {
    setChatBusy(true);
    setErr(null);
    try {
      const out = await api.post("/intake/chat", { state, message: message || null });
      setIntake(out.state);
      setView(out);
      setFromChat(out.booking_answers || {});
      if (urgentNow || out.done) {
        finishChat(urgentNow ? URGENT : out.assistant_message);
      } else {
        say("assistant", out.assistant_message);
      }
      return out;
    } catch (e) {
      setErr(e.message);
      return null;
    } finally {
      setChatBusy(false);
    }
  };

  const answerFlags = async (picked) => {
    setFlags(picked);
    const labels = questions.red_flags.filter((f) => picked.includes(f.code)).map((f) => f.label);
    say("patient", picked.length ? labels.join(", ") : "None of these");
    setStep("chat");
    // Now the chat reads the patient's description; with "None of these" it won't ask those warning signs again.
    const form = { ...(intake?.form || {}) };
    if (!picked.length) COVERED_BY_NONE.forEach((f) => { if (form[f] === undefined) form[f] = false; });
    await chat(reason, { ...(intake || {}), form }, picked.length > 0);
  };

  const send = (m) => {
    const msg = m.trim();
    if (!msg || chatBusy) return;
    setText("");
    say("patient", msg);
    if (step === "first") { // the description waits for the warning-sign check, then goes to the chat
      setReason(msg.slice(0, 500));
      say("assistant", "Thank you. Before I ask more: do you have any of these right now?");
      setStep("flags");
      return;
    }
    chat(msg, intake);
  };

  const answerQuick = (value, label) => {
    say("assistant", current.label);
    say("patient", label || current.options.find((o) => o.value === value)?.label || value);
    setAns((a) => {
      const next = { ...a, [current.id]: value };
      if (current.id === "chest_pain" && value === "no") ["cp_central", "cp_exertion", "cp_rest_relief"].forEach((k) => delete next[k]);
      if (current.id === "travel" && value === "no") delete next.travel_city;
      return next;
    });
  };

  // Progress: answers given, and roughly how many are left.
  const given = log.filter((m) => m.role === "patient").length;
  const chatLeft = step === "first" || step === "flags" ? CHAT_GUESS : step === "chat" ? (view?.remaining ?? CHAT_GUESS) : 0;
  const left = (step === "first" ? 2 : step === "flags" ? 1 : 0) + chatLeft + (step === "final" ? 0 : pending.length);
  const total = Math.max(given + left, 1);
  const pct = step === "final" ? 100 : Math.round((given / total) * 100);

  const submit = () => {
    setTried(true);
    if (!agree) return;
    const form = intake?.form ? { ...intake.form, consent_processing: true } : null;
    onSubmit({ reason: reason || "Not given", answers: { ...all, red_flags: flags || [] }, intake: form ? { form } : null, share });
  };

  return (
    <Card title="Tell us what's going on"
      subtitle={step === "final" ? "All done. Check the boxes below and send the request." : `About ${total} short questions. Most are one tap.`}
      actions={<Button size="sm" variant="secondary" icon={RotateCcw} disabled={chatBusy || busy} onClick={start}>Start over</Button>}>
      <div className="mb-3">
        <div className="mb-1 flex justify-between text-xs text-ink-500">
          <span>{step === "final" ? "Questions done" : `Question ${Math.min(given + 1, total)} of about ${total}`}</span>
          <span>The assistant doesn&apos;t diagnose or give medical advice.</span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-ink-100" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
          <div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>

      {urgent && (
        <div role="alert" className="mb-3 flex gap-3 rounded-xl border-2 border-red-300 bg-red-50 p-3 text-sm text-red-800">
          <AlertTriangle size={20} className="mt-0.5 shrink-0" />
          <div>
            <p className="font-bold">Please don&apos;t wait for this appointment: call 108 (ambulance) or go to the nearest emergency department now.</p>
            <p>You can still send this request; the doctor will be alerted.</p>
          </div>
        </div>
      )}

      <div ref={box} className="max-h-[26rem] min-h-[12rem] space-y-2.5 overflow-y-auto rounded-xl border border-ink-100 bg-white p-3" aria-live="polite">
        {log.map((m, i) => <Bubble key={i} role={m.role}>{m.text}</Bubble>)}
        {current && <Bubble role="assistant">{current.label}</Bubble>}
        {chatBusy && <Bubble role="assistant">…</Bubble>}
      </div>
      {err && <p role="alert" className="mt-2 text-sm font-semibold text-red-700">{err}</p>}

      <div className="mt-3">
        {step === "flags" && <FlagsInput flags={questions.red_flags} onDone={answerFlags} />}

        {(step === "chat" || step === "first") && !chatBusy && (
          <>
            {step === "chat" && !!view?.quick_replies?.length && (
              <div className="mb-2 flex flex-wrap gap-1.5">{view.quick_replies.map((c) => <Chip key={c} onClick={() => send(c)}>{c}</Chip>)}</div>
            )}
            <form onSubmit={(e) => { e.preventDefault(); send(text); }} className="flex gap-2">
              <input className={inputCls} value={text} maxLength={1000} aria-label="Your answer"
                placeholder={step === "first" ? "e.g. Fever and body pain for 3 days, headache behind the eyes" : "Type your answer…"}
                onChange={(e) => setText(e.target.value)} />
              <Button type="submit" icon={Send} disabled={!text.trim()}>Send</Button>
            </form>
            {step === "chat" && <button type="button" className="mt-2 text-xs font-semibold text-ink-500 hover:text-ink-800" onClick={() => finishChat("No problem. Just a few quick questions left.")}>Skip the rest of the chat</button>}
          </>
        )}

        {current && (current.kind === "city"
          ? <CityInput key={current.id} q={current} maxKm={questions.nearest_max_km} gps={current.id === "city"} known={current.id === "city" ? fromChat.city : undefined} onDone={answerQuick} />
          : <div className="flex flex-wrap gap-1.5">{current.options.map((o) => <Chip key={o.value} onClick={() => answerQuick(o.value)}>{o.label}</Chip>)}</div>)}

        {step === "final" && (
          <div className="space-y-3">
            <label className={`flex cursor-pointer items-start gap-2.5 rounded-xl p-2 text-sm text-ink-700 ${tried && !agree ? "bg-amber-50 ring-2 ring-amber-300" : ""}`}>
              <input type="checkbox" className="mt-0.5" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
              <span><span className="font-semibold text-ink-900">Share my answers with {doctorName} and save them to my health profile</span> <span className="text-red-600">*</span></span>
            </label>
            <label className="flex cursor-pointer items-start gap-2.5 p-2 text-sm text-ink-700">
              <input type="checkbox" className="mt-0.5" checked={share} onChange={(e) => setShare(e.target.checked)} />
              <span>
                <span className="font-semibold text-ink-900">Also let {doctorName} see my health records</span>
                <span className="block text-xs text-ink-500">Optional. You can change this any time on Doctor access.</span>
              </span>
            </label>
            {intake?.form?.reports_to_upload && (
              <Link to="/patient/upload" target="_blank" className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand-700">
                <Upload size={15} /> Upload your reports (opens in a new tab)
              </Link>
            )}
            <ErrorState error={error} />
            {tried && !agree && <p role="alert" className="text-sm font-semibold text-amber-800">Please tick the first box to send the request.</p>}
            {errorAction}
            <Button type="button" className="w-full" icon={CalendarCheck} loading={busy} onClick={submit}>Request appointment</Button>
            <p className="text-xs text-ink-500">The doctor confirms the request. You&apos;ll get a notification.</p>
          </div>
        )}
      </div>
    </Card>
  );
}
