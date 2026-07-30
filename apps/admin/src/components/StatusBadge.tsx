// Status badge — colors carry a redundant text label, never color-only.

const LABELS: Record<string, string> = {
  SUSPICIOUS: 'Подозрительно',
  CONSISTENT: 'Соответствует',
  INSUFFICIENT_DATA: 'Недостаточно данных',
  RUNNING: 'Анализ',
  QUEUED: 'В очереди',
  FAILED: 'Ошибка',
  SUCCEEDED: 'Готово',
  PENDING_UPLOAD: 'Ожидает',
  UPLOADING: 'Загружается',
  READY: 'Готово',
  DELETED: 'Удалено',
  PENDING: 'Ожидает согласия',
  GRANTED: 'Согласие дано',
  REVOKED: 'Согласие отозвано',
  DRAFT: 'Черновик',
  VALIDATED: 'Валидирован',
  SHADOW: 'Теневая',
  ACTIVE: 'Активная',
  RETIRED: 'Выведена',
  CONFIRMED_GENUINE: 'Подтверждено',
  CONFIRMED_SUSPICIOUS: 'Подтверждено подозрение',
  UNDECIDABLE: 'Не решено',
};

export function StatusBadge({ value }: { value: string }) {
  const cls = `badge badge--${value.toLowerCase()}`;
  return <span className={cls}>{LABELS[value] ?? value}</span>;
}
