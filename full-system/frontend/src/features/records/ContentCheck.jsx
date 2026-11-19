import { StatusBadge } from "../../components/ui";

/** Patient uploads are checked for medical content. Shown only when it could not be confirmed. */
export function ContentCheck({ doc }) {
  if (doc?.content_check !== "NOT_CHECKED") return null;
  return (
    <span title={doc.content_check_note || ""}>
      <StatusBadge variant="warning" icon={false}>Not confirmed as medical</StatusBadge>
    </span>
  );
}
