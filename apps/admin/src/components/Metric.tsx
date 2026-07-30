// Metric card.

export function Metric({
  label,
  value,
  detail,
  tone = 'default',
}: {
  label: string;
  value: string | number;
  detail?: string;
  tone?: 'default' | 'risk' | 'good' | 'info';
}) {
  return (
    <article className={`metric metric--${tone}`}>
      <div className="metric__label">{label}</div>
      <div className="metric__value">{value}</div>
      {detail && <div className="metric__detail">{detail}</div>}
    </article>
  );
}
