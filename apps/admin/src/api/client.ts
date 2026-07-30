import type { AnalysisJob } from '../types';
const API_BASE=import.meta.env.VITE_API_BASE_URL ?? '/api';
export class ApiError extends Error { constructor(public status:number, message:string){super(message)} }
async function request<T>(path:string, init?:RequestInit):Promise<T>{
  const response=await fetch(`${API_BASE}${path}`,{...init,headers:{'Content-Type':'application/json',...init?.headers}});
  if(!response.ok) throw new ApiError(response.status,await response.text());
  return response.json() as Promise<T>;
}
export const api={
  listJobs:():Promise<AnalysisJob[]>=>request('/v1/analysis-jobs'),
  getJob:(id:string):Promise<AnalysisJob>=>request(`/v1/analysis-jobs/${encodeURIComponent(id)}`),
  createReview:(decisionId:string,body:{verdict:string;reason:string})=>request(`/v1/reviews/${decisionId}`,{method:'POST',body:JSON.stringify(body)})
};
