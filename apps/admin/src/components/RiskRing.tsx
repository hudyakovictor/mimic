// Risk ring with conic-gradient.

export function RiskRing({ value }: { value: number }) {
  const v = Math.max(0, Math.min(1, value));
  const deg = Math.round(v * 360);
  const color = v >= 0.65 ? 'var(--danger)' : v >= 0.35 ? 'var(--warning)' : 'var(--success)';
  return (
    <div
      className="risk-ring"
      style={{
        background: `radial-gradient(closest-side, var(--surface) 75%, transparent 78% 99%), conic-gradient(${color} ${deg}deg, var(--surface-2) 0deg)`,
      }}
    >
      <div>
        <span>{Math.round(v * 100)}</span>
        <br />
        <small>риск / 100</small>
      </div>
    </div>
  );
}
