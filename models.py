"""Unified data model. No real student names are stored (Student ID only)."""
from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class StudentHealthReading:
    studentId: str
    timestamp: str
    skinTemperature: Optional[float]
    heartRate: Optional[float]
    signalQuality: float
    reportedSymptoms: List[str]
    cameraSource: str
    sensorSource: str
    status: str = "PENDING"          # NORMAL | REMEASURE | NURSE_REVIEW
    confidence: float = 0.0          # data-quality based confidence (see anomaly.py)
    validationStatus: str = "PENDING"  # VALID | INVALID
    # case-management fields
    id: str = ""
    reasons: List[str] = field(default_factory=list)
    action: str = ""
    followUp: str = "مفتوحة"
    notes: List[str] = field(default_factory=list)
    emergency: bool = False

    def to_dict(self):
        return asdict(self)
