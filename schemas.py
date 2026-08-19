from typing import Optional, List

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):

    message: str = Field(
        min_length=1,
        max_length=10000
    )

    document_id: Optional[str] = None


class Finding(BaseModel):

    page: Optional[int] = None

    clause: Optional[str] = None

    category: str

    severity: str

    description: str

    recommendation: Optional[str] = None


class LegalResponse(BaseModel):

    success: bool = True

    answer: str

    risk_level: str = "baixo"

    risk_score: int = 0

    confidence: float = 0.0

    requires_human_review: bool = True

    findings: List[Finding] = []

    unsupported_claims: List[str] = []

    scope_violation: bool = False

    guardrail_flags: List[str] = []

    document_id: Optional[str] = None


class DocumentAnalysisResponse(BaseModel):

    success: bool = True

    document_id: str

    filename: str

    summary: str

    risk_level: str

    risk_score: int

    confidence: float

    requires_human_review: bool

    findings: List[Finding]

    guardrail_flags: List[str] = []