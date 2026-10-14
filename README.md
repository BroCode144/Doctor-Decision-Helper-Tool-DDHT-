# DDHT — Doctor Decision Helper Tool

A frontend prototype of a healthcare record management system where **patients**
manage their own medical records and **doctors** can access a patient's records
only when strict, explicit conditions are met.

This is an **academic prototype**. It is not a production medical system, does
not provide medical advice, and is not intended for real clinical use.

## Purpose

DDHT demonstrates a centralized system for:

- **Patients** to view, manage, and upload their own medical records, and to
  control exactly which doctors can see them.
- **Doctors** to search for patients and view their history — but only for
  patients who meet the platform's access rule (see below).
- **Administrators** to manage users, verify doctors, and audit every access
  attempt made on the platform.

## No AI

This prototype intentionally contains **no AI, LLM, RAG, embeddings, vector
databases, LangChain, external AI APIs, OCR, or automated medical
recommendations of any kind**. All diagnoses, prescriptions, consultations,
and record data are predefined, static mock data or data created through the
UI by the user during a session. Any AI capability for the broader DDHT
project is explicitly out of scope for this build.

## The core access-control rule

This is the single most important business rule in the application:

> A doctor may access a patient's medical records **only if**:
> 1. The doctor has previously treated the patient, **AND**
> 2. The patient has explicitly authorized that doctor to view their records.
>
> If either condition is false, access is denied — no exceptions.

This logic lives in one place, `src/utils/accessControl.js`
(`canAccessPatient`, `grantAccess`, `revokeAccess`), and every UI surface —
patient search, dashboards, consent management — reads from it rather than
hardcoding access decisions.

When access is denied, **no medical data is ever rendered** — not diagnoses,
prescriptions, history, consultations, or documents. Only the patient's name
and the specific denial reason are shown.

## Features

- **Role-based login** for Patient, Doctor, and Administrator, with one-click
  demo account fill-in and easy account switching.
- **Doctor workspace**: dashboard with stats and recent activity, patient
  search with a visually explicit access-decision panel, and (once access is
  granted) tabs for Profile, Timeline, Medical Records, Diagnoses,
  Prescriptions, Consultations, and Documents.
- **Patient portal**: dashboard, profile, medical records (with type/date
  filtering), chronological medical timeline, document upload (simulated),
  and consent management to grant/revoke doctor access in real time.
- **Admin console**: system-wide dashboard, user management (view,
  activate/deactivate), doctor verification, and a full access-history audit
  log (every granted and denied attempt, with reasons).
- **Consistent design system**: sidebar/header navigation, dashboard cards,
  status badges (icon + text, never color alone), tables, timelines, modals,
  toasts, search/filter bars, empty states, and error messages.
- **Record preservation**: records and documents added by doctors can never be
  deleted. A patient can delete only a document they uploaded themselves
  (after a confirmation step); doctors and admins have no delete option.
- **Responsive layout**: usable from mobile through desktop, with a
  collapsible sidebar on small screens.

## Technology stack

- [React 19](https://react.dev/) + [Vite](https://vite.dev/)
- [React Router v7](https://reactrouter.com/) for client-side routing
- [Tailwind CSS v4](https://tailwindcss.com/) for styling
- [lucide-react](https://lucide.dev/) for icons
- Plain JavaScript (JSX), no TypeScript
- All data is **mock data held in React state** (Context API) — there is no
  backend, database, or server. Changes made during a session (uploads,
  consent grants/revokes, user activation, doctor verification) live only in
  memory and reset on a full page reload.

## Installation & running

```bash
npm install
npm run dev
```

Then open the URL Vite prints (typically `http://localhost:5173`).

Other scripts:

```bash
npm run build     # production build
npm run preview   # preview the production build
npm run lint       # run oxlint
```

## Demo credentials

All demo accounts are shown directly on the login page with one-click fill.

| Role          | Email               | Password    | Notes                                   |
|---------------|----------------------|-------------|------------------------------------------|
| Doctor        | doctor@ddht.demo     | doctor123   | Dr. Raj Mehta — General Physician        |
| Patient       | patient@ddht.demo    | patient123  | Rahul Sharma — has an authorized doctor  |
| Administrator | admin@ddht.demo      | admin123    | Meera Joshi — system administrator       |

Additional demo doctors and patients (same password pattern: `doctor123` /
`patient123`) are seeded for a richer demo — see `src/data/mockData.js`.

## Main user flows

### Doctor: access granted

Login as Doctor → Patient Search → search "Rahul Sharma" → both
`previouslyVisited` and `authorized` are `true` → **Access Granted** → full
profile, history, timeline, records, diagnoses, prescriptions, consultations,
and documents become visible.

### Doctor: access denied (not authorized)

Search "Priya Shah" → previously treated, but **not authorized** → **Access
Denied** — "The patient has not authorized you to access their medical
records." No medical data is shown.

### Doctor: access denied (never treated)

Search "Aman Patel" → authorized, but **never previously treated** →
**Access Denied** — "You have not previously treated this patient." No
medical data is shown.

### Patient: consent revoke

Login as Patient (Rahul Sharma) → Consent Management → Revoke Access on
Dr. Raj Mehta → log back in as that doctor and search for Rahul again →
access is now denied immediately, reflecting the revoked consent.

### Admin: verification & audit

Login as Administrator → Doctor Verification → verify a pending doctor →
Access History → see every granted/denied attempt across the system, with
filters by result and doctor.

## Prototype limitations

- **No backend or persistence.** All state lives in memory via React
  Context. A full page reload (or closing the tab) resets everything back to
  the seeded mock data.
- **No real authentication.** Login is a simple mock credential check against
  a static user list — not suitable for production use.
- **No real file storage.** "Uploaded" documents are simulated: metadata is
  recorded and a text preview is generated, but no actual file is stored or
  transmitted anywhere.
- **No AI, medical reasoning, or decision support** of any kind — this is
  intentional and out of scope for this build.
- Data is fictional and for demonstration only; it does not represent real
  patients, doctors, or medical records.

---

DDHT Prototype — Academic Demonstration Only.
