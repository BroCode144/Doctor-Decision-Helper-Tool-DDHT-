import { useNavigate } from "react-router-dom";
import { Card, PageHeader } from "../../components/ui";
import UploadForm from "../../features/records/UploadForm";

export default function PatientUpload() {
  const navigate = useNavigate();
  return (
    <div>
      <PageHeader title="Upload a medical document" subtitle="Lab reports, prescriptions, imaging reports, discharge summaries or consultation documents. Files are attached to your own record only." />
      <Card>
        <UploadForm mode="patient" onUploaded={() => setTimeout(() => navigate("/patient/documents"), 1800)} />
      </Card>
    </div>
  );
}
