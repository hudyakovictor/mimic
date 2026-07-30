"""Object key generators — consistent across services.

MG-STUB: final.
"""
from __future__ import annotations

import uuid


def asset_key(tenant_id: uuid.UUID, asset_id: uuid.UUID, ext: str = "mp4") -> str:
    return f"{tenant_id}/videos/{asset_id}.{ext.lstrip('.')}"


def landmarks_key(tenant_id: uuid.UUID, job_id: uuid.UUID) -> str:
    return f"{tenant_id}/derived/{job_id}/landmarks.mgml"


def landmarks_npz_key(tenant_id: uuid.UUID, job_id: uuid.UUID) -> str:
    return f"{tenant_id}/derived/{job_id}/landmarks.npz"


def transcript_key(tenant_id: uuid.UUID, job_id: uuid.UUID) -> str:
    return f"{tenant_id}/derived/{job_id}/transcript.json"


def features_key(tenant_id: uuid.UUID, job_id: uuid.UUID) -> str:
    return f"{tenant_id}/derived/{job_id}/features.npz"


def phrase_landmarks_key(tenant_id: uuid.UUID, sample_id: uuid.UUID) -> str:
    return f"{tenant_id}/clips/{sample_id}/landmarks.mgml"


def clip_key(tenant_id: uuid.UUID, sample_id: uuid.UUID) -> str:
    return f"{tenant_id}/clips/{sample_id}/video.mp4"


def audio_clip_key(tenant_id: uuid.UUID, sample_id: uuid.UUID) -> str:
    return f"{tenant_id}/clips/{sample_id}/audio.wav"


def template_curve_key(tenant_id: uuid.UUID, template_id: uuid.UUID) -> str:
    return f"{tenant_id}/templates/{template_id}/mean_curve.npy"


def template_cov_key(tenant_id: uuid.UUID, template_id: uuid.UUID) -> str:
    return f"{tenant_id}/templates/{template_id}/cov_diag.npy"


def model_key(model_id: uuid.UUID, version: str) -> str:
    return f"{model_id}/{version}/model.bin"


def audit_export_key(tenant_id: uuid.UUID, export_id: uuid.UUID, ext: str = "csv") -> str:
    return f"{tenant_id}/{export_id}.{ext}"


def audio_key(tenant_id: uuid.UUID, job_id: uuid.UUID) -> str:
    return f"{tenant_id}/derived/{job_id}/audio.wav"
