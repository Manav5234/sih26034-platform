import enum


class VerificationState(str, enum.Enum):
    SATISFIED = "SATISFIED"
    VIOLATION = "VIOLATION"
    NOT_VERIFIED = "NOT_VERIFIED"
    CONFLICT = "CONFLICT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvidenceSourceType(str, enum.Enum):
    OCR = "OCR"
    BARCODE = "BARCODE"
    QR = "QR"
    PRODUCT_DATABASE = "PRODUCT_DATABASE"
    MANUAL_ENTRY = "MANUAL_ENTRY"
    OFFICER_CORRECTION = "OFFICER_CORRECTION"
    PRIOR_RECORD = "PRIOR_RECORD"


class OfficerRole(str, enum.Enum):
    ADMIN = "ADMIN"
    INSPECTOR = "INSPECTOR"
    VIEWER = "VIEWER"


class ScanStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
