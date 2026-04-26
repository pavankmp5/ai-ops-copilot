from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.auth import User, require_roles
from app.services.orchestrator import answer_general_question, answer_question

router = APIRouter(tags=["query"])


class AskRequest(BaseModel):
    question: str
    dataset_id: str


class GeneralAskRequest(BaseModel):
    question: str


class LatencyResponse(BaseModel):
    total: float
    rag: float
    llm: float


class AskResponse(BaseModel):
    question: str
    dataset_id: str | None = None
    tenant_id: str
    requested_by: str
    mode: str
    answer_source: str = Field(description="Either 'llm' or 'local_fallback'.")
    rag_used: bool
    latency_ms: LatencyResponse
    answer: str


@router.post("/ask", response_model=AskResponse)
def ask_question(
    request: AskRequest,
    current_user: User = Depends(require_roles("admin", "user")),
):
    return answer_question(request.question, request.dataset_id, current_user)


@router.post("/chat", response_model=AskResponse)
def ask_general_question(
    request: GeneralAskRequest,
    current_user: User = Depends(require_roles("admin", "user")),
):
    return answer_general_question(request.question, current_user)
