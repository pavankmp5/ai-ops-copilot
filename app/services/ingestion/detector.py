from __future__ import annotations

import mimetypes
import os

from fastapi import HTTPException, status

SUPPORTED_EXTENSIONS = {".csv", ".pdf", ".txt", ".md", ".markdown", ".docx"}

MIME_BY_EXTENSION = {
    ".csv": "text/csv",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def detect_file_type(filename: str, content_type: str | None = None) -> tuple[str, str]:
    cleaned_name = (filename or "").strip()
    extension = os.path.splitext(cleaned_name.lower())[1]
    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{extension or 'unknown'}'. Supported: {supported}",
        )

    mime_type = (content_type or "").strip().lower()
    if not mime_type:
        mime_type = MIME_BY_EXTENSION.get(extension) or (mimetypes.guess_type(cleaned_name)[0] or "application/octet-stream")

    return extension, mime_type
