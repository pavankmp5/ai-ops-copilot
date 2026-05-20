from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.auth import User, authorize, get_current_user
from app.services.orchestrator import answer_general_question, answer_question
from app.services.conversations import create_chat_session, get_chat_session_detail, list_chat_sessions

router = APIRouter(tags=["query"])


class AskRequest(BaseModel):
    question: str
    dataset_id: str
    session_id: str | None = None


class GeneralAskRequest(BaseModel):
    question: str
    session_id: str | None = None


class CreateSessionRequest(BaseModel):
    title: str | None = None


class SessionMessageRequest(BaseModel):
    question: str
    dataset_id: str | None = None


class LatencyResponse(BaseModel):
    total: float
    rag: float
    llm: float


class AskResponse(BaseModel):
    session_id: str
    message_id: str
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
    current_user: User = Depends(get_current_user),
):
    authorize("datasets.query", current_user)
    return answer_question(request.question, request.dataset_id, current_user, request.session_id)


@router.post("/chat", response_model=AskResponse)
def ask_general_question(
    request: GeneralAskRequest,
    current_user: User = Depends(get_current_user),
):
    authorize("datasets.query", current_user)
    return answer_general_question(request.question, current_user, request.session_id)


@router.post("/chat/sessions")
def create_session(
    request: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
):
    authorize("datasets.query", current_user)
    return create_chat_session(current_user, request.title)


@router.get("/chat/sessions")
def list_sessions(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    authorize("datasets.query", current_user)
    return list_chat_sessions(current_user, limit=limit)


@router.get("/chat/sessions/{session_id}")
def get_session_detail(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    authorize("datasets.query", current_user)
    return get_chat_session_detail(session_id, current_user)


@router.post("/chat/sessions/{session_id}/messages", response_model=AskResponse)
def append_session_message(
    session_id: str,
    request: SessionMessageRequest,
    current_user: User = Depends(get_current_user),
):
    authorize("datasets.query", current_user)
    if request.dataset_id:
        return answer_question(request.question, request.dataset_id, current_user, session_id)
    return answer_general_question(request.question, current_user, session_id)
