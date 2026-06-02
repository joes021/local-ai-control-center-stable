type StatusCardProps = {
  label: string;
  value: string;
};

export function StatusCard({ label, value }: StatusCardProps) {
  return (
    <section className="status-card">
      <span className="status-label">{label}</span>
      <strong className="status-value">{value}</strong>
    </section>
  );
}
