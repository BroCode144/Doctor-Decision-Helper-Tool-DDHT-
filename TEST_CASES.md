# DDHT — Test Cases and Results

All test cases for the DDHT prototype, grouped by area, with the requirement each
one verifies. Every case below was run against the prototype on 13 Oct 2026.

- **Logic tests (U)** call the access-control and data-helper functions directly.
- **Browser tests (A–E)** drive the running app the way a user would: logging in,
  clicking through pages, typing, uploading, and switching roles in one session.

**Result: 116 of 116 test cases pass.** Two defects were found and fixed (see
[Defects found](#defects-found)).

Demo accounts used: Doctor `doctor@ddht.demo` (Dr. Raj Mehta), Patient
`patient@ddht.demo` (Rahul Sharma), Admin `admin@ddht.demo` (Meera Joshi), plus
`priya@ddht.demo` and `vikram@ddht.demo` for account-status tests.

## U. Core logic (14)

| ID | Test case | Requirement | Result |
|---|---|---|---|
| U01 | Treated **and** authorized (D001 → P001) is granted, with no denial reason | PNFR-02 | Pass |
| U02 | Treated but not authorized (D001 → P002) is denied: "not authorized" | PNFR-02 | Pass |
| U03 | Authorized but never treated (D001 → P003) is denied: "not previously treated" | PNFR-02 | Pass |
| U04 | Neither condition (D001 → P004) is denied with the combined reason | PNFR-02 | Pass |
| U05 | No doctor–patient relationship (D001 → P005) is denied: "no record of this patient" | PNFR-02 | Pass |
| U06 | Revoke then grant flips access, and never changes the original list | PFR-19, PNFR-12 | Pass |
| U07 | Granting a doctor who never treated the patient still denies access | PNFR-02 | Pass |
| U08 | Every lookup helper returns only the requested patient's items | PNFR-04 | Pass |
| U09 | Every patient's timeline is sorted newest first | PFR-08 | Pass |
| U10 | Every record points at an existing patient and doctor | PNFR-09 | Pass |
| U11 | Every medical record's document name has a matching document | PNFR-09, PFR-09 | Pass (after fix) |
| U12 | IDs are unique in every data list | PNFR-09 | Pass |
| U13 | Every user account links to a real patient/doctor/admin; all 3 demo logins exist | PFR-01 | Pass |
| U14 | Date formatting and age calculation handle valid and empty input | PNFR-10 | Pass |

## A. Login, logout and role protection (17)

| ID | Test case | Requirement | Result |
|---|---|---|---|
| A01 | Submitting an empty login form shows "Please enter both an email and a password." | PNFR-10 | Pass |
| A02 | Wrong password shows "Invalid email or password." and stays on the login page | PFR-01, PNFR-10 | Pass |
| A03 | Doctor login lands on the doctor dashboard (/doctor) | PFR-01 | Pass |
| A04 | Doctor sidebar shows exactly: Dashboard, Patient Search, My Access History | PFR-02, PNFR-06 | Pass |
| A05 | Header shows the logged-in doctor's name | PNFR-06 | Pass |
| A06 | Doctor opening /admin is sent back to /doctor | PFR-02 | Pass |
| A07 | Doctor opening /patient/records is sent back to /doctor | PFR-02 | Pass |
| A08 | An unknown URL redirects to the user's own home page | PNFR-10 | Pass |
| A09 | Log out returns to /login | PFR-03 | Pass |
| A10 | Logging out clears the saved session | PFR-03, PNFR-01 | Pass |
| A11 | A logged-out user opening /doctor/search is sent to /login | PFR-02, PNFR-01 | Pass |
| A12 | Patient login works with extra spaces and capital letters in the email | PFR-01 | Pass |
| A13 | Patient sidebar shows its 6 pages | PFR-02, PNFR-06 | Pass |
| A14 | Patient opening /admin/users is sent back to /patient | PFR-02 | Pass |
| A15 | Admin login lands on /admin | PFR-01 | Pass |
| A16 | Admin sidebar shows exactly: Dashboard, User Management, Doctor Verification, Access History | PFR-02, PNFR-06 | Pass |
| A17 | Admin opening /doctor/search is sent back to /admin | PFR-02 | Pass |

## B. Doctor (28)

| ID | Test case | Requirement | Result |
|---|---|---|---|
| B01 | Patient Search lists "My patients": Rahul Sharma, Priya Shah, Neha Kapoor | PFR-05 | Pass |
| B02 | Searching "rahul" finds only Rahul Sharma | PFR-05 | Pass |
| B03 | Searching by ID "p003" finds Aman Patel | PFR-05 | Pass |
| B04 | A search with no match shows a "No patients found" message | PNFR-10 | Pass |
| B05 | No medical tabs are shown before a patient is opened | PNFR-03 | Pass |
| B06 | Opening Rahul Sharma shows "Access granted" | PFR-05, PNFR-02 | Pass |
| B07 | All 7 tabs appear when granted (Profile, Timeline, Medical Records, Diagnoses, Prescriptions, Consultations, Documents) | PFR-07 | Pass |
| B08 | Profile tab shows blood group and emergency contact | PFR-06 | Pass |
| B09 | Timeline tab lists events newest first | PFR-08 | Pass |
| B10 | Medical Records tab lists the patient's records | PFR-07, PFR-12 | Pass |
| B11 | Filtering by type "Prescription" shows only prescriptions | PFR-10 | Pass |
| B12 | "View" on the Amlodipine prescription record opens its document | PFR-09 | Pass (after fix) |
| B13 | Filtering by date 2026-08-20 shows only records from that date | PFR-10 | Pass |
| B14a | Diagnoses tab shows the patient's diagnoses | PFR-13 | Pass |
| B14b | Prescriptions tab shows the patient's prescriptions | PFR-14 | Pass |
| B14c | Consultations tab shows the patient's consultations | PFR-15 | Pass |
| B15 | Doctor sees documents with "View Document" and no Delete button | PFR-09, PNFR-11 | Pass |
| B16 | The document viewer opens with a preview | PFR-09 | Pass |
| B17 | Pressing Escape closes the document viewer | PNFR-05 | Pass |
| B18 | Priya Shah is denied ("has not authorized you"), with no medical data shown | PNFR-02, PNFR-03 | Pass |
| B19 | Aman Patel is denied ("not previously treated"), with no medical data shown | PNFR-02, PNFR-03 | Pass |
| B20 | Sneha Iyer is denied with the combined reason, with no medical data shown | PNFR-02, PNFR-03 | Pass |
| B21 | Vikram Desai is denied ("no record of this patient"), with no medical data shown | PNFR-02, PNFR-03 | Pass |
| B22 | My Access History shows the session's granted and denied attempts | PFR-23 | Pass |
| B23 | Doctor dashboard shows the welcome message, stats and recent access attempts | PFR-04 | Pass |
| B24 | Dashboard quick search finds Neha Kapoor | PFR-04 | Pass |
| B25 | A fresh doctor dashboard shows no patient the doctor never treated (no Aman Patel) | PFR-04, PNFR-03 | Pass |
| B26 | "Recently Accessed Patients" lists only patients whose records were opened (Rahul Sharma), not denied attempts | PFR-04 | Pass |

## C. Patient (23)

| ID | Test case | Requirement | Result |
|---|---|---|---|
| C01 | Patient dashboard shows the welcome message, recent records, consent status and quick actions | PFR-16 | Pass |
| C02 | My Profile shows Rahul Sharma, P001 and blood group | PFR-17, PFR-06 | Pass |
| C03 | My Medical Records explains that doctors' records cannot be deleted | PNFR-11 | Pass |
| C04 | Filtering own records by type "Lab Report" works | PFR-10, PFR-17 | Pass |
| C05a | Own Diagnoses tab shows data | PFR-13, PFR-17 | Pass |
| C05b | Own Prescriptions tab shows data | PFR-14, PFR-17 | Pass |
| C05c | Own Consultations tab shows data | PFR-15, PFR-17 | Pass |
| C06 | Only the patient's own upload (Blood Test Report) has a Delete button | PNFR-11 | Pass |
| C07 | Medical Timeline lists events newest first | PFR-08, PFR-17 | Pass |
| C08 | Uploading with empty fields shows "Please fill in the document name, hospital, and date…" | PFR-11, PNFR-10 | Pass |
| C09 | A valid upload goes to My Medical Records with "Medical record uploaded successfully." | PFR-11, PFR-18 | Pass |
| C10 | The uploaded record appears in the records table | PFR-11, PFR-18 | Pass |
| C11 | "View" on the uploaded record opens its document | PFR-09 | Pass |
| C12 | The uploaded imaging record appears on the timeline | PFR-08 | Pass |
| C13 | The uploaded document shows a Delete button | PNFR-11 | Pass |
| C14 | Clicking Delete then Cancel keeps the document | PNFR-11 | Pass |
| C15 | Confirming Delete removes the document and shows "was deleted." | PNFR-11 | Pass |
| C16 | Deleting the upload also removes its record; record count returns to the original | PNFR-11, PNFR-09 | Pass |
| C17 | Consent Management lists Rahul's doctors (Dr. Raj Mehta, Dr. Anjali Shah) | PFR-19 | Pass |
| C18 | Revoking Dr. Raj Mehta shows a message and offers "Grant Access" | PFR-19 | Pass |
| C19 | After revoking, Dr. Raj Mehta is denied Rahul's records ("has not authorized you") | PFR-19, PNFR-02 | Pass |
| C20 | Granting access again shows a message | PFR-19 | Pass |
| C21 | After re-granting, Dr. Raj Mehta is granted access again | PFR-19, PNFR-02 | Pass |

## D. Admin (18)

| ID | Test case | Requirement | Result |
|---|---|---|---|
| D01 | An inactive account (Vikram) cannot log in and sees "This account has been deactivated…" | PFR-21, PNFR-01 | Pass |
| D02 | Admin dashboard shows 10 users, 6 patients, 3 doctors, 2 / 3 verified doctors | PFR-20 | Pass |
| D03 | Admin dashboard shows recent access activity | PFR-20, PFR-23 | Pass |
| D04 | User Management lists all 10 users | PFR-21 | Pass |
| D05 | Searching "priya" shows only Priya Shah | PFR-21 | Pass |
| D06 | Role filter "Doctor" shows only the 3 doctors | PFR-21 | Pass |
| D07 | "View" opens Priya Shah's user details | PFR-21 | Pass |
| D08 | Deactivate sets Priya Shah to Inactive | PFR-21 | Pass |
| D09 | Deactivated Priya can no longer log in | PFR-21, PNFR-01 | Pass |
| D10 | Activate sets Priya Shah back to Active | PFR-21 | Pass |
| D11 | Re-activated Priya can log in again | PFR-21 | Pass |
| D12 | Dr. Kabir Nair starts as Pending | PFR-22 | Pass |
| D13 | Verify marks Dr. Kabir Nair as Verified | PFR-22 | Pass |
| D14 | Dashboard verified count updates from 2 / 3 to 3 / 3 | PFR-20, PFR-22 | Pass |
| D15 | Mark as Pending returns Dr. Kabir Nair to Pending (count back to 2 / 3) | PFR-22 | Pass |
| D16 | Access History lists all attempts, including the session's | PFR-23 | Pass |
| D17 | Filter Result = Denied shows only denied attempts, with reasons | PFR-23 | Pass |
| D18 | Filter Doctor = Dr. Anjali Shah shows only her attempts | PFR-23 | Pass |

## E. Phone screens, refresh and errors (16)

| ID | Test case | Requirement | Result |
|---|---|---|---|
| E01–E13 | Each of the 13 logged-in pages (4 admin, 3 doctor, 6 patient) fits a 375 px phone screen with no sideways scrolling | PNFR-05, PNFR-07 | Pass |
| E14 | On a phone the sidebar is hidden and opens from the menu button | PNFR-06 | Pass |
| E15 | Refreshing the page keeps the user logged in on the same page | PNFR-01 | Pass |
| E16 | Loading every page fresh produces no errors in the browser console | PNFR-10 | Pass |

## Defects found

| # | Defect | Effect | Fix | Re-test |
|---|---|---|---|---|
| 1 | 4 medical records named documents that did not exist: "Prescription — Amlodipine" (Rahul Sharma), "Consultation Note — Allergic Rhinitis" (Priya Shah), "Consultation Note — Chest Discomfort" (Sneha Iyer), "Consultation Note — Knee Injury" (Vikram Desai) | Clicking **View** on those records did nothing | Added the 4 documents (DOC-4009 to DOC-4012) to `src/data/mockData.js`, using only the details already in each patient's consultation, diagnosis and prescription | U11, B12 pass |
| 2 | The doctor dashboard showed Aman Patel, a patient Dr. Raj Mehta never treated: a sample access-log entry recorded a denied attempt on him, and "Recently Accessed Patients" also listed denied attempts | A doctor saw a stranger on their own dashboard | Removed that sample entry from `src/data/mockData.js`; "Recently Accessed Patients" in `DoctorDashboard.jsx` now lists only granted accesses | B25, B26 pass |

## Notes

- All data lives in the browser. Refreshing the page resets uploads, deletions,
  consent changes and admin changes to the sample data; this is expected for the prototype.
- Doctor verification (PFR-22) records a doctor's status; it does not block an
  unverified doctor from signing in. The requirements do not ask for that.
