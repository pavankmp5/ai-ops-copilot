import logging

from fastapi import HTTPException, status
from openai import OpenAI

from app.core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

client = OpenAI(
    api_key=settings.openrouter_api_key,
    base_url=settings.openrouter_base_url,
    max_retries=settings.llm_max_retries,
    timeout=settings.llm_timeout_seconds,
)


def ask_llm(prompt: str):
    if not settings.openrouter_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM provider is not configured. Set OPENROUTER_API_KEY.",
        )

    logger.info("Calling LLM with prompt length %s", len(prompt))

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": "You are a business analyst."},
            {"role": "user", "content": prompt},
        ],
    )

    logger.info("LLM response received successfully")
    return response.choices[0].message.content
