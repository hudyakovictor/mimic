from ..domain import NormalizedSequence


class VersionedMotionScorer:
    """Production scoring adapter contract.

    MG-STUB: load a signed ONNX/CoreML model and its calibration artifact. The implementation
    must verify feature schema, model checksum and threshold profile before inference.
    """
    model_version = "unconfigured"
    def score(self, probe: NormalizedSequence, baseline_uri: str):
        raise NotImplementedError("MG-STUB: no validated motion model configured")
