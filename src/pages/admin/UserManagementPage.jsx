import { useState } from "react";
import { Eye } from "lucide-react";
import { useData } from "../../context/DataContext";
import { useToast } from "../../context/ToastContext";
import DataTable from "../../components/ui/DataTable";
import StatusBadge from "../../components/ui/StatusBadge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import SearchBar from "../../components/ui/SearchBar";
import FilterBar from "../../components/ui/FilterBar";
import { formatDate } from "../../utils/dataHelpers";

const ROLE_LABEL = { patient: "Patient", doctor: "Doctor", admin: "Administrator" };

export default function UserManagementPage() {
  const { users, toggleUserStatus } = useData();
  const { showToast } = useToast();
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("All");
  const [viewingUser, setViewingUser] = useState(null);

  const filtered = users.filter((u) => {
    const q = query.trim().toLowerCase();
    const matchesQuery =
      !q || u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q);
    const matchesRole = roleFilter === "All" || u.role === roleFilter;
    return matchesQuery && matchesRole;
  });

  const handleToggle = (u) => {
    toggleUserStatus(u.id);
    showToast(
      `${u.name} is now ${u.status === "Active" ? "deactivated" : "activated"}.`,
      "info"
    );
  };

  const columns = [
    { key: "name", header: "Name" },
    { key: "linkedId", header: "User ID" },
    {
      key: "role",
      header: "Role",
      render: (row) => <StatusBadge variant="neutral">{ROLE_LABEL[row.role]}</StatusBadge>,
    },
    { key: "email", header: "Email" },
    {
      key: "status",
      header: "Status",
      render: (row) => (
        <StatusBadge variant={row.status === "Active" ? "success" : "danger"}>
          {row.status}
        </StatusBadge>
      ),
    },
    {
      key: "registeredOn",
      header: "Registration Date",
      render: (row) => formatDate(row.registeredOn),
    },
    {
      key: "actions",
      header: "Actions",
      render: (row) => (
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" icon={Eye} onClick={() => setViewingUser(row)}>
            View
          </Button>
          <Button
            variant={row.status === "Active" ? "danger" : "primary"}
            size="sm"
            onClick={() => handleToggle(row)}
          >
            {row.status === "Active" ? "Deactivate" : "Activate"}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-lg font-bold text-ink-900">User Management</h2>
        <p className="mt-1 text-sm text-ink-500">
          View and manage all registered patients, doctors, and administrators.
        </p>
      </div>

      <div className="flex flex-col gap-4 rounded-2xl border border-ink-100 bg-white p-5 shadow-sm sm:flex-row sm:items-end sm:justify-between">
        <div className="w-full sm:max-w-sm">
          <SearchBar value={query} onChange={setQuery} placeholder="Search by name or email..." />
        </div>
        <FilterBar
          filters={[
            {
              label: "Role",
              value: roleFilter,
              onChange: setRoleFilter,
              options: [
                { value: "All", label: "All Roles" },
                { value: "patient", label: "Patient" },
                { value: "doctor", label: "Doctor" },
                { value: "admin", label: "Administrator" },
              ],
            },
          ]}
        />
      </div>

      <DataTable columns={columns} data={filtered} emptyMessage="No users match your search." />

      <Modal
        open={!!viewingUser}
        onClose={() => setViewingUser(null)}
        title="User Details"
        size="sm"
        footer={
          <Button variant="secondary" onClick={() => setViewingUser(null)}>
            Close
          </Button>
        }
      >
        {viewingUser && (
          <dl className="space-y-3 text-sm">
            <div>
              <dt className="text-xs font-medium text-ink-400">Name</dt>
              <dd className="font-medium text-ink-800">{viewingUser.name}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-ink-400">User ID</dt>
              <dd className="font-medium text-ink-800">{viewingUser.linkedId}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-ink-400">Role</dt>
              <dd className="font-medium text-ink-800">{ROLE_LABEL[viewingUser.role]}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-ink-400">Email</dt>
              <dd className="font-medium text-ink-800">{viewingUser.email}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-ink-400">Status</dt>
              <dd>
                <StatusBadge variant={viewingUser.status === "Active" ? "success" : "danger"}>
                  {viewingUser.status}
                </StatusBadge>
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-ink-400">Registration Date</dt>
              <dd className="font-medium text-ink-800">{formatDate(viewingUser.registeredOn)}</dd>
            </div>
          </dl>
        )}
      </Modal>
    </div>
  );
}
