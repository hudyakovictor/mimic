"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-30

MG-STUB: final — creates all tables, indexes, and append-only triggers.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Helpers
def _json_type():
    return postgresql.JSONB(astext_type=sa.Text())


def _array_type(elem):
    return postgresql.ARRAY(elem)


def upgrade() -> None:
    # tenants
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("settings", _json_type(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("roles", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    # subjects
    op.create_table(
        "subjects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("consent_state", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("retention_policy", _json_type(), nullable=False, server_default="{}"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "external_id", name="uq_subjects_tenant_external"),
    )

    # enrollments
    op.create_table(
        "enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("signed_by", sa.String(255)),
        sa.Column("evidence_uri", sa.String(512)),
        sa.Column("ip", sa.String(64)),
        sa.Column("user_agent", sa.String(512)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # assets (append-only)
    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_url", sa.String(1024)),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("mime", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("sha256", sa.String(64)),
        sa.Column("duration_ms", sa.BigInteger),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
        sa.Column("fps", sa.Float),
        sa.Column("has_audio", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("state", sa.String(32), nullable=False, server_default="PENDING_UPLOAD"),
        sa.Column("failure_reason", sa.Text),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(512)),
        sa.Column("extra", _json_type(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_assets_state", "assets", ["state"])
    op.create_index("ix_assets_created_at", "assets", ["created_at"])

    # analysis_jobs
    op.create_table(
        "analysis_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id"), nullable=False, index=True),
        sa.Column("pipeline_version", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="QUEUED"),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
        sa.Column("last_error", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("asset_id", "subject_id", "pipeline_version", name="uq_jobs_idempotency"),
    )
    op.create_index("ix_jobs_state", "analysis_jobs", ["state"])

    # job_stages
    op.create_table(
        "job_stages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("output_uri", sa.String(512)),
        sa.Column("error", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
        sa.Column("output_metadata", _json_type(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("job_id", "name", "attempt", name="uq_job_stages_unique"),
    )

    # landmark_sequences
    op.create_table(
        "landmark_sequences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("track_id", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("frame_count", sa.Integer, nullable=False),
        sa.Column("source_fps", sa.Float, nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("quality_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("quality_failures", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # transcripts
    op.create_table(
        "transcripts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("words", _json_type(), nullable=False, server_default="[]"),
        sa.Column("object_key", sa.String(512)),
        sa.Column("mean_word_confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # decisions (append-only)
    op.create_table(
        "decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("label", sa.String(32), nullable=False),
        sa.Column("risk_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("quality_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("model_checksum", sa.String(128), nullable=False, server_default=""),
        sa.Column("evidence", _json_type(), nullable=False, server_default="[]"),
        sa.Column("phrase_instances", _json_type(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # reviews (append-only)
    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("decisions.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # phrase_templates (immutable: new version per update)
    op.create_table(
        "phrase_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="SET NULL"), index=True),
        sa.Column("word", sa.String(128), nullable=False, index=True),
        sa.Column("language", sa.String(16), nullable=False, server_default="en"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True)),
        sa.Column("n_samples", sa.Integer, nullable=False, server_default="0"),
        sa.Column("mean_curve_object_key", sa.String(512), nullable=False),
        sa.Column("cov_diag_object_key", sa.String(512), nullable=False),
        sa.Column("regional_stats", _json_type(), nullable=False, server_default="{}"),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("is_mature", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("state", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_phrase_templates_word_lang", "phrase_templates", ["word", "language"])

    # phrase_samples (immutable)
    op.create_table(
        "phrase_samples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("phrase_templates.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("decisions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reviews.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("word", sa.String(128), nullable=False, index=True),
        sa.Column("language", sa.String(16), nullable=False, server_default="en"),
        sa.Column("start_ms", sa.Integer, nullable=False),
        sa.Column("end_ms", sa.Integer, nullable=False),
        sa.Column("video_clip_object_key", sa.String(512), nullable=False),
        sa.Column("landmarks_object_key", sa.String(512), nullable=False),
        sa.Column("audio_clip_object_key", sa.String(512)),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("n_frames", sa.Integer, nullable=False, server_default="0"),
        sa.Column("mean_dtw_to_template", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # model_versions
    op.create_table(
        "model_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("artifact_checksum", sa.String(128), nullable=False),
        sa.Column("code_commit", sa.String(64), nullable=False, server_default=""),
        sa.Column("feature_schema", sa.String(64), nullable=False, server_default=""),
        sa.Column("training_dataset_manifest", _json_type(), nullable=False, server_default="{}"),
        sa.Column("evaluation_report", _json_type(), nullable=False, server_default="{}"),
        sa.Column("calibration_profile", _json_type(), nullable=False, server_default="{}"),
        sa.Column("intended_use", sa.Text, nullable=False, server_default=""),
        sa.Column("known_limitations", sa.Text, nullable=False, server_default=""),
        sa.Column("state", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("approver_id", postgresql.UUID(as_uuid=True)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("promoted_by", postgresql.UUID(as_uuid=True)),
        sa.Column("promoted_at", sa.DateTime(timezone=True)),
        sa.Column("promotion_reason", sa.Text),
        sa.Column("version_", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("kind", "version", name="uq_model_kind_version"),
    )
    op.create_index("ix_models_state", "model_versions", ["state"])

    # audit_events (append-only)
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), index=True),
        sa.Column("action", sa.String(64), nullable=False, index=True),
        sa.Column("resource_type", sa.String(64), nullable=False, index=True),
        sa.Column("resource_id", sa.String(64), index=True),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("ip", sa.String(64)),
        sa.Column("user_agent", sa.String(512)),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), index=True),
        sa.Column("reason", sa.Text),
        sa.Column("extra", _json_type(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # outbox_events
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_name", sa.String(128), nullable=False, index=True),
        sa.Column("payload", _json_type(), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), index=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), index=True),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_outbox_unpublished", "outbox_events", ["created_at"], postgresql_where=sa.text("published_at IS NULL"))

    # Append-only triggers
    op.execute("""
    CREATE OR REPLACE FUNCTION deny_mutation() RETURNS TRIGGER AS $$
    BEGIN
      RAISE EXCEPTION 'Append-only table %; UPDATE/DELETE forbidden', TG_TABLE_NAME;
    END;
    $$ LANGUAGE plpgsql;
    """)

    for table in ("decisions", "reviews", "audit_events", "phrase_samples"):
        op.execute(f"""
        CREATE TRIGGER {table}_no_mutation
        BEFORE UPDATE OR DELETE ON {table}
        FOR EACH ROW EXECUTE FUNCTION deny_mutation();
        """)

    # pgcrypto for gen_random_uuid
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")


def downgrade() -> None:
    for table in ("decisions", "reviews", "audit_events", "phrase_samples"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_no_mutation ON {table};")
    op.execute("DROP FUNCTION IF EXISTS deny_mutation();")
    op.drop_table("outbox_events")
    op.drop_table("audit_events")
    op.drop_table("model_versions")
    op.drop_table("phrase_samples")
    op.drop_table("phrase_templates")
    op.drop_table("reviews")
    op.drop_table("decisions")
    op.drop_table("transcripts")
    op.drop_table("landmark_sequences")
    op.drop_table("job_stages")
    op.drop_table("analysis_jobs")
    op.drop_table("assets")
    op.drop_table("enrollments")
    op.drop_table("subjects")
    op.drop_table("users")
    op.drop_table("tenants")
