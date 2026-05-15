export function LoadingState({ label = "Loading" }: { label?: string }) {
  return <div className="state-block">{label}...</div>;
}

export function ErrorState({ message }: { message: string }) {
  return <div className="state-block error">{message}</div>;
}

export function EmptyState({ label = "No records found" }: { label?: string }) {
  return <div className="state-block">{label}</div>;
}
