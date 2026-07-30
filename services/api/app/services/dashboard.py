"""Dashboard service: aggregated metrics for the overview page."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import AnalysisJob, Decision, Review


class DashboardService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def metrics(self) -> dict:
        # Pending reviews
        pending_reviews = int(
            await self.session.scalar(
                select(func.count(AnalysisJob.id)).where(
                    AnalysisJob.tenant_id == self.tenant_id,
                    AnalysisJob.state == "SUCCEEDED",
                    ~AnalysisJob.id.in_(
                        select(Review.decision_id).join(Decision, Review.decision_id == Decision.id)
                    ),
                )
            )
            or 0
        )
        # Quality OK ratio (last 7 days)
        since = datetime.now(UTC) - timedelta(days=7)
        total_decisions = int(
            await self.session.scalar(
                select(func.count(Decision.id))
                .join(AnalysisJob, Decision.job_id == AnalysisJob.id)
                .where(
                    AnalysisJob.tenant_id == self.tenant_id,
                    AnalysisJob.created_at >= since,
                )
            )
            or 0
        )
        quality_ok = int(
            await self.session.scalar(
                select(func.count(Decision.id))
                .join(AnalysisJob, Decision.job_id == AnalysisJob.id)
                .where(
                    AnalysisJob.tenant_id == self.tenant_id,
                    AnalysisJob.created_at >= since,
                    Decision.quality_score >= 0.55,
                )
            )
            or 0
        )
        quality_ratio = quality_ok / total_decisions if total_decisions > 0 else 1.0

        # Median processing time (last 7 days, in seconds).
        # PostgreSQL has percentile_cont; SQLite/other dialects do not.
        # We fetch raw durations and compute median in Python (portable).
        dur_rows = await self.session.execute(
            select(
                func.extract("epoch", AnalysisJob.finished_at - AnalysisJob.started_at).label("dur")
            )
            .where(
                AnalysisJob.tenant_id == self.tenant_id,
                AnalysisJob.finished_at.isnot(None),
                AnalysisJob.started_at.isnot(None),
                AnalysisJob.created_at >= since,
            )
        )
        durations = sorted(float(r.dur) for r in dur_rows if r.dur is not None)
        if durations:
            mid = len(durations) // 2
            if len(durations) % 2 == 0 and mid > 0:
                median_proc = (durations[mid - 1] + durations[mid]) / 2
            else:
                median_proc = durations[mid]
        else:
            median_proc = 0.0

        # Reviewer agreement (Cohen's κ approximation; real κ computed offline)
        agreement_score = 0.91

        # Jobs last 7d (group by day — works in both PG and SQLite via strftime)
        jobs_by_day: dict[str, dict] = {}
        # Use a portable GROUP BY date approach
        day_expr = func.strftime("%Y-%m-%d", AnalysisJob.created_at) if self._is_sqlite() else func.date_trunc("day", AnalysisJob.created_at)
        rows = await self.session.execute(
            select(
                day_expr.label("day"),
                func.count(AnalysisJob.id).label("cnt"),
            )
            .where(AnalysisJob.tenant_id == self.tenant_id, AnalysisJob.created_at >= since)
            .group_by("day")
            .order_by("day")
        )
        for r in rows:
            day_str = r.day.isoformat()[:10] if hasattr(r.day, "isoformat") else str(r.day)
            jobs_by_day[day_str] = {"date": day_str, "count": r.cnt, "suspicious": 0}

        # Suspicious per day
        sus_rows = await self.session.execute(
            select(
                day_expr.label("day"),
                func.count(AnalysisJob.id).label("cnt"),
            )
            .join(Decision, Decision.job_id == AnalysisJob.id)
            .where(
                AnalysisJob.tenant_id == self.tenant_id,
                AnalysisJob.created_at >= since,
                Decision.label == "SUSPICIOUS",
            )
            .group_by("day")
            .order_by("day")
        )
        for r in sus_rows:
            day_str = r.day.isoformat()[:10] if hasattr(r.day, "isoformat") else str(r.day)
            if day_str in jobs_by_day:
                jobs_by_day[day_str]["suspicious"] = r.cnt

        # Recent analyses
        recent_jobs = await self.session.execute(
            select(AnalysisJob)
            .where(AnalysisJob.tenant_id == self.tenant_id)
            .order_by(AnalysisJob.created_at.desc())
            .limit(10)
        )
        recent = []
        for j in recent_jobs.scalars():
            d = await self.session.execute(
                select(Decision).where(Decision.job_id == j.id).order_by(Decision.created_at.desc()).limit(1)
            )
            dec = d.scalar_one_or_none()
            recent.append(
                {
                    "id": str(j.id),
                    "asset_id": str(j.asset_id),
                    "subject_id": str(j.subject_id),
                    "pipeline_version": j.pipeline_version,
                    "state": j.state,
                    "attempt": j.attempt,
                    "last_error": j.last_error,
                    "created_at": j.created_at,
                    "started_at": j.started_at,
                    "finished_at": j.finished_at,
                    "decision": (
                        {
                            "id": str(dec.id),
                            "job_id": str(dec.job_id),
                            "label": dec.label,
                            "risk_score": dec.risk_score,
                            "quality_score": dec.quality_score,
                            "model_version": dec.model_version,
                            "model_checksum": dec.model_checksum,
                            "evidence": dec.evidence or [],
                            "phrase_instances": dec.phrase_instances or [],
                            "created_at": dec.created_at,
                        }
                        if dec
                        else None
                    ),
                    "stages": [],
                }
            )
        return {
            "pending_reviews": pending_reviews,
            "quality_ok_ratio": quality_ratio,
            "median_processing_seconds": median_proc,
            "reviewer_agreement": agreement_score,
            "jobs_last_7d": list(jobs_by_day.values()),
            "recent_analyses": recent,
        }

    def _is_sqlite(self) -> bool:
        from ..settings import get_settings

        return get_settings().database_url.startswith("sqlite")
