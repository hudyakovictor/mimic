from .services import AnalysisJobService, ReviewService

def get_analysis_service() -> AnalysisJobService:
    """MG-STUB: application composition root; wire SQL repositories and transactional outbox."""
    raise NotImplementedError("MG-STUB: persistence composition is not configured")

def get_review_service() -> ReviewService:
    """MG-STUB: wire review repository and authenticated reviewer context."""
    raise NotImplementedError("MG-STUB: review composition is not configured")
