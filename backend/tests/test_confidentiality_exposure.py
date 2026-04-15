from __future__ import annotations

from app.services.phi import confidentiality_exposure_level


def test_confidentiality_exposure_level_thresholds():
    assert confidentiality_exposure_level(None) is None
    assert confidentiality_exposure_level(0) == "LOW"
    assert confidentiality_exposure_level(33) == "LOW"
    assert confidentiality_exposure_level(34) == "MEDIUM"
    assert confidentiality_exposure_level(50) == "MEDIUM"
    assert confidentiality_exposure_level(66) == "MEDIUM"
    assert confidentiality_exposure_level(67) == "HIGH"
    assert confidentiality_exposure_level(100) == "HIGH"

