import { Link } from "react-router-dom";
import { UploadCloud } from "lucide-react";
import { useAuth } from "../../context/contexts";
import { api } from "../../lib/api";
import { useApi } from "../../hooks/useApi";
import { Button, Card, ErrorState, Loading, PageHeader } from "../../components/ui";
import { DocumentsTable } from "../../features/records";
import { useDocumentViewer } from "../../hooks/useDocumentViewer";

export default function PatientDocuments() {
  const { user } = useAuth();
  const [viewer, openDoc] = useDocumentViewer();
  const { data, loading, error, reload } = useApi(() => api.get(`/patients/${user.patient_id}/documents`), [user.patient_id]);
  return (
    <div>
      {viewer}
      <PageHeader title="My documents" subtitle="Documents uploaded by you, your doctors, or the records office."
        actions={<Link to="/patient/upload"><Button icon={UploadCloud}>Upload document</Button></Link>} />
      {loading && <Loading />}
      <ErrorState error={error} onRetry={reload} />
      {data && <Card padded={false}><DocumentsTable documents={data} onView={openDoc} onDeleted={reload} /></Card>}
    </div>
  );
}
