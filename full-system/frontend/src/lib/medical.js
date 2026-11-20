/** Groups medicines into one prescription per visit (same record, or same doctor and day). */
export function groupPrescriptions(items = []) {
  const groups = new Map();
  for (const x of items) {
    const key = x.record_id || `${x.doctor?.id || "?"}-${x.date}`;
    if (!groups.has(key)) groups.set(key, { key, date: x.date, doctor: x.doctor, record_id: x.record_id, medicines: [] });
    groups.get(key).medicines.push(x);
  }
  return [...groups.values()].sort((a, b) => b.date.localeCompare(a.date));
}
