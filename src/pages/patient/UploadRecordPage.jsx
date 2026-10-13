import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { UploadCloud, FileCheck2 } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useData } from "../../context/DataContext";
import { useToast } from "../../context/ToastContext";
import { RECORD_TYPES } from "../../data/mockData";
import Button from "../../components/ui/Button";
import ErrorMessage from "../../components/ui/ErrorMessage";

const TODAY = new Date().toISOString().slice(0, 10);

export default function UploadRecordPage() {
  const { user } = useAuth();
  const { addMedicalRecord } = useData();
  const { showToast } = useToast();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    documentName: "",
    type: RECORD_TYPES[0],
    date: TODAY,
    hospital: "",
    description: "",
  });
  const [fileName, setFileName] = useState("");
  const [error, setError] = useState("");

  const update = (field, value) => setForm((prev) => ({ ...prev, [field]: value }));

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    setFileName(file ? file.name : "");
    if (file && !form.documentName) {
      update("documentName", file.name.replace(/\.[^/.]+$/, ""));
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setError("");

    if (!form.documentName.trim() || !form.hospital.trim() || !form.date) {
      setError("Please fill in the document name, hospital, and date before uploading.");
      return;
    }

    addMedicalRecord({
      patientId: user.linkedId,
      doctorId: null,
      type: form.type,
      date: form.date,
      hospital: form.hospital.trim(),
      documentName: form.documentName.trim(),
      description: form.description.trim() || "Uploaded by patient.",
      uploadedBy: user.name,
      preview: [
        `Patient: ${user.name} (${user.linkedId})`,
        `Document: ${form.documentName.trim()}`,
        fileName ? `Original file: ${fileName}` : "No file attached (prototype simulation)",
        `Uploaded by: ${user.name}`,
        `Date: ${form.date}`,
      ],
    });

    showToast("Medical record uploaded successfully.", "success");
    navigate("/patient/records");
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h2 className="font-display text-lg font-bold text-ink-900">Upload Medical Record</h2>
        <p className="mt-1 text-sm text-ink-500">
          Add a new document to your medical records. This is simulated for the
          prototype — no files are sent to a server.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="space-y-5 rounded-2xl border border-ink-100 bg-white p-6 shadow-sm"
      >
        {error && <ErrorMessage message={error} />}

        <div>
          <label htmlFor="file" className="mb-1.5 block text-sm font-medium text-ink-700">
            File (simulated upload)
          </label>
          <label
            htmlFor="file"
            className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-ink-200 bg-ink-50/50 px-4 py-8 text-center hover:border-brand-300"
          >
            <UploadCloud size={24} className="text-ink-400" />
            <span className="text-sm font-medium text-ink-600">
              {fileName ? (
                <span className="inline-flex items-center gap-1.5 text-brand-700">
                  <FileCheck2 size={15} /> {fileName}
                </span>
              ) : (
                "Click to choose a file, or drag and drop"
              )}
            </span>
            <span className="text-xs text-ink-400">PDF, JPG, or PNG — mock upload only</span>
            <input id="file" type="file" className="hidden" onChange={handleFileChange} />
          </label>
        </div>

        <div>
          <label htmlFor="documentName" className="mb-1.5 block text-sm font-medium text-ink-700">
            Document Name
          </label>
          <input
            id="documentName"
            type="text"
            value={form.documentName}
            onChange={(e) => update("documentName", e.target.value)}
            placeholder="e.g. Blood Test Report — March 2026"
            className="w-full rounded-xl border border-ink-200 px-4 py-2.5 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
          />
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="type" className="mb-1.5 block text-sm font-medium text-ink-700">
              Record Type
            </label>
            <select
              id="type"
              value={form.type}
              onChange={(e) => update("type", e.target.value)}
              className="w-full rounded-xl border border-ink-200 px-4 py-2.5 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
            >
              {RECORD_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="date" className="mb-1.5 block text-sm font-medium text-ink-700">
              Date
            </label>
            <input
              id="date"
              type="date"
              value={form.date}
              max={TODAY}
              onChange={(e) => update("date", e.target.value)}
              className="w-full rounded-xl border border-ink-200 px-4 py-2.5 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
            />
          </div>
        </div>

        <div>
          <label htmlFor="hospital" className="mb-1.5 block text-sm font-medium text-ink-700">
            Hospital / Clinic
          </label>
          <input
            id="hospital"
            type="text"
            value={form.hospital}
            onChange={(e) => update("hospital", e.target.value)}
            placeholder="e.g. City Diagnostics"
            className="w-full rounded-xl border border-ink-200 px-4 py-2.5 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
          />
        </div>

        <div>
          <label htmlFor="description" className="mb-1.5 block text-sm font-medium text-ink-700">
            Notes (optional)
          </label>
          <textarea
            id="description"
            rows={3}
            value={form.description}
            onChange={(e) => update("description", e.target.value)}
            placeholder="Any additional context for this record..."
            className="w-full rounded-xl border border-ink-200 px-4 py-2.5 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
          />
        </div>

        <Button type="submit" icon={UploadCloud} className="w-full">
          Upload Record
        </Button>
      </form>
    </div>
  );
}
