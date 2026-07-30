from uuid import UUID
from fastapi import APIRouter, Depends, status
from ..dependencies import get_review_service
from ..schemas import CreateReview
from ..services import ReviewService
router = APIRouter(prefix="/reviews", tags=["reviews"])
@router.post("/{decision_id}", status_code=status.HTTP_201_CREATED)
async def create_review(decision_id: UUID, command: CreateReview, service: ReviewService = Depends(get_review_service)):
    # MG-STUB: reviewer_id must come from verified JWT claims, never request payload.
    reviewer_id = UUID("00000000-0000-0000-0000-000000000000")
    return {"review_id": str(await service.create(decision_id, command, reviewer_id))}
