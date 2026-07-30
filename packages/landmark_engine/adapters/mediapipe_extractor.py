from typing import BinaryIO

from ..domain import LandmarkSequence


class MediaPipeLandmarkExtractor:
    """Reference extraction adapter.

    MG-STUB: implement only after golden-video fixtures and coordinate mapping are approved.
    Required behavior:
    - decode timestamps from the media time base, never from loop counters;
    - detect and track one requested face track;
    - map MediaPipe points to the semantic v1 schema;
    - emit confidence and head pose per frame;
    - never interpolate gaps here; quality policy owns that decision.
    """
    def extract(self, video: BinaryIO, *, track_id: str) -> LandmarkSequence:
        raise NotImplementedError("MG-STUB: calibrated MediaPipe extraction adapter is not installed")
