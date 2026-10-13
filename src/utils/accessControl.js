// ---------------------------------------------------------------------------
// Centralized doctor -> patient access-control logic.
//
// THE CORE RULE (must never be bypassed or hardcoded elsewhere):
// A doctor may access a patient's medical records ONLY when BOTH are true:
//   1. previouslyVisited === true  (the patient was previously treated by
//      this doctor)
//   2. authorized === true         (the patient has explicitly granted this
//      doctor consent to view their records)
// If either condition is false, access MUST be denied.
// ---------------------------------------------------------------------------

export const DENIAL_REASONS = {
  NOT_TREATED: "You have not previously treated this patient.",
  NOT_AUTHORIZED:
    "The patient has not authorized you to access their medical records.",
  BOTH:
    "You have not previously treated this patient, and the patient has not authorized you to access their medical records.",
  NO_RELATIONSHIP: "No record of this patient exists for you as a doctor.",
};

/**
 * Determine whether a doctor can access a given patient's records.
 *
 * @param {Array} accessList - list of { doctorId, patientId, previouslyVisited, authorized }
 * @param {string} doctorId
 * @param {string} patientId
 * @returns {{ granted: boolean, previouslyVisited: boolean, authorized: boolean, reason: string|null }}
 */
export function canAccessPatient(accessList, doctorId, patientId) {
  const relationship = accessList.find(
    (entry) => entry.doctorId === doctorId && entry.patientId === patientId
  );

  if (!relationship) {
    return {
      granted: false,
      previouslyVisited: false,
      authorized: false,
      reason: DENIAL_REASONS.NO_RELATIONSHIP,
    };
  }

  const { previouslyVisited, authorized } = relationship;
  const granted = previouslyVisited === true && authorized === true;

  let reason = null;
  if (!granted) {
    if (!previouslyVisited && !authorized) {
      reason = DENIAL_REASONS.BOTH;
    } else if (!previouslyVisited) {
      reason = DENIAL_REASONS.NOT_TREATED;
    } else if (!authorized) {
      reason = DENIAL_REASONS.NOT_AUTHORIZED;
    }
  }

  return { granted, previouslyVisited, authorized, reason };
}

/**
 * Returns a new access list with the given doctor granted authorization
 * by the patient. Does not mutate the input array.
 */
export function grantAccess(accessList, doctorId, patientId) {
  const exists = accessList.some(
    (entry) => entry.doctorId === doctorId && entry.patientId === patientId
  );

  if (!exists) {
    return [
      ...accessList,
      { doctorId, patientId, previouslyVisited: false, authorized: true },
    ];
  }

  return accessList.map((entry) =>
    entry.doctorId === doctorId && entry.patientId === patientId
      ? { ...entry, authorized: true }
      : entry
  );
}

/**
 * Returns a new access list with the given doctor's authorization revoked
 * by the patient. Does not mutate the input array.
 */
export function revokeAccess(accessList, doctorId, patientId) {
  return accessList.map((entry) =>
    entry.doctorId === doctorId && entry.patientId === patientId
      ? { ...entry, authorized: false }
      : entry
  );
}
