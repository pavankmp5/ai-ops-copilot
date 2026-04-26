import logging
from io import BytesIO

import pandas as pd
from fastapi import HTTPException, UploadFile, status

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

    print("Guardrail passed: question validated")
    logger.info("Question guardrail passed with length %s", len(cleaned_question))
    return cleaned_question


async def validate_csv_upload(file: UploadFile) -> tuple[bytes, pd.DataFrame]:
    settings = get_settings()
    filename = file.filename or ""

    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV uploads are supported.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded CSV file is empty.",
        )

    if len(file_bytes) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV exceeds {settings.max_upload_size_bytes} bytes.",
        )

    try:
        dataframe = pd.read_csv(BytesIO(file_bytes))
    except Exception as exc:
        logger.exception("CSV parsing failed for file '%s'", filename)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid CSV file.",
        ) from exc

    print("Guardrail passed: CSV validated")
    logger.info("CSV guardrail passed for '%s' with %s rows", filename, len(dataframe))
    return file_bytes, dataframe
