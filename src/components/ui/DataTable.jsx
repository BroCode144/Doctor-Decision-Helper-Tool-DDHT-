import EmptyState from "./EmptyState";

export default function DataTable({ columns, data, keyField = "id", emptyMessage = "No data available." }) {
  if (!data || data.length === 0) {
    return <EmptyState message={emptyMessage} />;
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-ink-100 bg-white shadow-sm">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead>
          <tr className="border-b border-ink-100 bg-ink-50/60">
            {columns.map((col) => (
              <th
                key={col.key}
                scope="col"
                className="px-4 py-3 font-semibold text-ink-500 whitespace-nowrap"
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr
              key={row[keyField]}
              className="border-b border-ink-50 last:border-0 hover:bg-ink-50/60 transition-colors"
            >
              {columns.map((col) => (
                <td key={col.key} className="px-4 py-3 align-middle text-ink-800">
                  {col.render ? col.render(row) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
