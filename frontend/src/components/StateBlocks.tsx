export function LoadingState({ label = "Loading" }: { label?: string }) {
  return <div className="state-block">{label}...</div>;
}

export function ErrorState({ message }: { message: string }) {
  return <div className="state-block error">{message}</div>;
}

export function ErrorList({ messages }: { messages: Array<string | null | undefined> }) {
  const unique = Array.from(new Set(messages.filter((message): message is string => Boolean(message))));
  return (
    <>
      {unique.map((message) => (
        <ErrorState key={message} message={message} />
      ))}
    </>
  );
}

export function EmptyState({ label = "No records found" }: { label?: string }) {
  return <div className="state-block">{label}</div>;
}
