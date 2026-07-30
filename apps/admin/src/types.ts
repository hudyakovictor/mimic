export type JobStatus='QUEUED'|'RUNNING'|'SUCCEEDED'|'FAILED'|'INSUFFICIENT_DATA';
export type DecisionLabel='CONSISTENT'|'SUSPICIOUS'|'INSUFFICIENT_DATA';
export interface Evidence {code:string; contribution:number; message:string; startMs?:number; endMs?:number}
export interface Decision {label:DecisionLabel; riskScore:number; qualityScore:number; modelVersion:string; evidence:Evidence[]}
export interface AnalysisJob {id:string; subject:string; assetName:string; status:JobStatus; createdAt:string; decision?:Decision}
