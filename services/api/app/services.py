from uuid import UUID
from .ports import AnalysisJobRepository, ReviewRepository, EventPublisher
from .schemas import AnalysisJob, CreateAnalysisJob, CreateReview

class AnalysisJobService:
    def __init__(self, jobs: AnalysisJobRepository, events: EventPublisher): self.jobs, self.events = jobs, events
    async def create(self, command: CreateAnalysisJob) -> AnalysisJob:
        job = await self.jobs.create(command)
        await self.events.publish_outbox("analysis.requested.v1", {"job_id": str(job.id), "asset_id": str(command.asset_id)})
        return job
    async def get(self, job_id: UUID) -> AnalysisJob | None: return await self.jobs.get(job_id)

class ReviewService:
    def __init__(self, reviews: ReviewRepository, events: EventPublisher): self.reviews, self.events = reviews, events
    async def create(self, decision_id: UUID, command: CreateReview, reviewer_id: UUID) -> UUID:
        review_id = await self.reviews.create(decision_id, command, reviewer_id)
        await self.events.publish_outbox("review.created.v1", {"review_id": str(review_id), "decision_id": str(decision_id)})
        return review_id
