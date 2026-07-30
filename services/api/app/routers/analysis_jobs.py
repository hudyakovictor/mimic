from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from ..dependencies import get_analysis_service
from ..schemas import AnalysisJob, CreateAnalysisJob
from ..services import AnalysisJobService
router = APIRouter(prefix="/analysis-jobs", tags=["analysis"])
@router.post("", response_model=AnalysisJob, status_code=status.HTTP_202_ACCEPTED)
async def create_job(command: CreateAnalysisJob, service: AnalysisJobService = Depends(get_analysis_service)):
    return await service.create(command)
@router.get("/{job_id}", response_model=AnalysisJob)
async def get_job(job_id: UUID, service: AnalysisJobService = Depends(get_analysis_service)):
    job = await service.get(job_id)
    if not job: raise HTTPException(status_code=404, detail="Analysis job not found")
    return job
