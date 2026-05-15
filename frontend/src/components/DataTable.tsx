import { isValidElement } from "react";

import { EmptyState } from "./StateBlocks";

type Props = {
  rows: Record<string, unknown>[];
  columns?: string[];
};

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export default function DataTable({ rows, columns }: Props) {
  if (!rows.length) return <EmptyState />;
  const keys = columns ?? Object.keys(rows[0]).slice(0, 10);
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {keys.map((key) => (
              <th key={key}>{key.replaceAll("_", " ")}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {keys.map((key) => (
                <td key={key}>{isValidElement(row[key]) ? row[key] : formatValue(row[key])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
