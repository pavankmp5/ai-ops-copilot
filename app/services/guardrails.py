import logging

from fastapi import HTTPException, status

from app.core.settings import get_settings

logger = logging.getLogger(__name__)


def validate_question(question: str) -> str:
    settings = get_settings()
    cleaned_question = question.strip()

    if not cleaned_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty.",
        )

    if len(cleaned_question) > settings.max_question_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Question exceeds {settings.max_question_length} characters.",
        )

    logger.info("Question guardrail passed with length %s", len(cleaned_question))
    return cleaned_question
