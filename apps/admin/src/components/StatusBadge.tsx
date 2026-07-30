import type { DecisionLabel,JobStatus } from '../types';
const labels:Record<string,string>={SUSPICIOUS:'Подозрительно',CONSISTENT:'Соответствует',INSUFFICIENT_DATA:'Недостаточно данных',RUNNING:'Анализ',QUEUED:'В очереди',FAILED:'Ошибка',SUCCEEDED:'Готово'};
export function StatusBadge({value}:{value:DecisionLabel|JobStatus}){return <span className={`badge badge--${value.toLowerCase()}`}>{labels[value]??value}</span>}
