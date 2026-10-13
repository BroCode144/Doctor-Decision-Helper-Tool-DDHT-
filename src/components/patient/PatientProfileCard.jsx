import { Cake, Phone, Mail, Droplet, MapPin, UserRound, Contact } from "lucide-react";
import { calculateAge, formatDate } from "../../utils/dataHelpers";

function InfoRow({ icon: Icon, label, value }) {
  return (
    <div className="flex items-start gap-3">
      <div className="rounded-lg bg-ink-100 p-2 text-ink-500">
        <Icon size={16} />
      </div>
      <div>
        <p className="text-xs font-medium text-ink-400">{label}</p>
        <p className="text-sm font-medium text-ink-800">{value || "—"}</p>
      </div>
    </div>
  );
}

export default function PatientProfileCard({ patient }) {
  return (
    <div className="rounded-2xl border border-ink-100 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-4 border-b border-ink-100 pb-5">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-100 text-xl font-bold text-brand-700">
          {patient.initials}
        </div>
        <div>
          <h3 className="font-display text-xl font-bold text-ink-900">{patient.name}</h3>
          <p className="text-sm text-ink-500">
            Patient ID: {patient.id} · {calculateAge(patient.dob)} years · {patient.gender}
          </p>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <InfoRow icon={Cake} label="Date of Birth" value={formatDate(patient.dob)} />
        <InfoRow icon={UserRound} label="Gender" value={patient.gender} />
        <InfoRow icon={Phone} label="Phone" value={patient.phone} />
        <InfoRow icon={Mail} label="Email" value={patient.email} />
        <InfoRow icon={Droplet} label="Blood Group" value={patient.bloodGroup} />
        <InfoRow icon={MapPin} label="Address" value={patient.address} />
        <InfoRow icon={Contact} label="Emergency Contact" value={patient.emergencyContact} />
      </div>
    </div>
  );
}
