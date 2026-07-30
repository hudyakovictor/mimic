from fastapi import FastAPI
from .routers import analysis_jobs, reviews, health

app = FastAPI(title="MimicGuard API", version="0.1.0")
app.include_router(health.router)
app.include_router(analysis_jobs.router, prefix="/v1")
app.include_router(reviews.router, prefix="/v1")
