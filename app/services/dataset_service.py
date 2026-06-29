import hashlib
import logging
import os
import uuid

from fastapi import HTTPException, UploadFile, status
from app.core.auth import User
from app.services.access import (
    assign_dataset_owner,
    get_dataset_id_by_hash,
    grant_dataset_access,
    list_dataset_records,
    register_dataset_hash,
)
from app.services.audit import record_audit_event
from app.services.ingestion.pipeline import parse_uploaded_document
from app.services.storage import dataset_exists, save_dataset_csv, save_dataset_file

logger = logging.getLogger(__name__)


async def upload_dataset(file: UploadFile, current_user: User) -> dict:
    filename = file.filename or "dataset.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV uploads are supported on /upload-csv.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded CSV file is empty.",
        )

    parsed_document = parse_uploaded_document(
        filename=filename,
        content_type=file.content_type,
        content=file_bytes,
    )
    rows = int(parsed_document.metadata.get("rows", 0) or 0)
    parsed_columns = parsed_document.metadata.get("columns") or []

    # Keep current CSV analytics behavior by storing normalized CSV bytes.
    normalized_csv_bytes = file_bytes
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    existing_dataset_id = get_dataset_id_by_hash(file_hash, current_user.tenant_id)

    if existing_dataset_id:
        if dataset_exists(existing_dataset_id):
            grant_dataset_access(current_user.username, existing_dataset_id, granted_by_username=current_user.username)
            record_audit_event(
                event_type="dataset.reuse",
                actor_username=current_user.username,
                tenant_id=current_user.tenant_id,
                resource_type="dataset",
                resource_id=existing_dataset_id,
                detail=f"Reused duplicate upload '{file.filename}'.",
            )
            logger.info(
                "User '%s' reused dataset '%s' for file '%s'",
                current_user.username,
                existing_dataset_id,
                file.filename,
            )
            return {
                "message": "File already exists. Reusing stored dataset.",
                "dataset_id": existing_dataset_id,
                "filename": file.filename,
                "reused": True,
            }
        # Recover from metadata-only datasets by recreating the missing backing file.
        save_dataset_csv(existing_dataset_id, normalized_csv_bytes)
        grant_dataset_access(current_user.username, existing_dataset_id, granted_by_username=current_user.username)
        record_audit_event(
            event_type="dataset.recovered",
            actor_username=current_user.username,
            tenant_id=current_user.tenant_id,
            resource_type="dataset",
            resource_id=existing_dataset_id,
            detail=f"Recovered missing dataset file for '{file.filename}'.",
        )
        logger.warning(
            "Recovered missing dataset file for dataset '%s' via upload by user '%s'",
            existing_dataset_id,
            current_user.username,
        )
        return {
            "message": "Recovered dataset file from uploaded content.",
            "dataset_id": existing_dataset_id,
            "tenant_id": current_user.tenant_id,
            "filename": file.filename,
            "rows": rows if rows > 0 else None,
            "columns": parsed_columns if parsed_columns else None,
            "reused": False,
            "indexing": "pending",
        }

    dataset_id = str(uuid.uuid4())
    save_dataset_csv(dataset_id, normalized_csv_bytes)

    assign_dataset_owner(
        dataset_id,
        current_user.username,
        current_user.tenant_id,
        file_hash,
        file.filename or f"{dataset_id}.csv",
    )
    grant_dataset_access(current_user.username, dataset_id, granted_by_username=current_user.username)
    register_dataset_hash(dataset_id, file_hash)

    logger.info(
        "User '%s' uploaded dataset '%s' from file '%s'",
        current_user.username,
        dataset_id,
        file.filename,
    )

    return {
        "message": "File stored",
        "dataset_id": dataset_id,
        "tenant_id": current_user.tenant_id,
        "filename": file.filename,
        "rows": rows if rows > 0 else None,
        "columns": parsed_columns if parsed_columns else None,
        "indexing": "pending",
    }


async def upload_document(file: UploadFile, current_user: User) -> dict:
    settings_max = 5 * 1024 * 1024
    from app.core.settings import get_settings

    settings_max = get_settings().max_upload_size_bytes
    filename = (file.filename or "document.txt").strip()
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded document is empty.",
        )
    if len(file_bytes) > settings_max:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document exceeds {settings_max} bytes.",
        )

    parsed_document = parse_uploaded_document(
        filename=filename,
        content_type=file.content_type,
        content=file_bytes,
    )
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    existing_dataset_id = get_dataset_id_by_hash(file_hash, current_user.tenant_id)

    if existing_dataset_id:
        if dataset_exists(existing_dataset_id, filename):
            grant_dataset_access(current_user.username, existing_dataset_id, granted_by_username=current_user.username)
            record_audit_event(
                event_type="dataset.reuse",
                actor_username=current_user.username,
                tenant_id=current_user.tenant_id,
                resource_type="dataset",
                resource_id=existing_dataset_id,
                detail=f"Reused duplicate upload '{filename}'.",
            )
            return {
                "message": "File already exists. Reusing stored dataset.",
                "dataset_id": existing_dataset_id,
                "filename": filename,
                "reused": True,
                "indexing": "existing",
            }

        save_dataset_file(existing_dataset_id, filename, file_bytes, content_type=file.content_type)
        grant_dataset_access(current_user.username, existing_dataset_id, granted_by_username=current_user.username)
        return {
            "message": "Recovered dataset file from uploaded content.",
            "dataset_id": existing_dataset_id,
            "tenant_id": current_user.tenant_id,
            "filename": filename,
            "rows": parsed_document.metadata.get("rows"),
            "columns": None,
            "reused": False,
            "indexing": "pending",
        }

    dataset_id = str(uuid.uuid4())
    save_dataset_file(dataset_id, filename, file_bytes, content_type=file.content_type)
    assign_dataset_owner(
        dataset_id,
        current_user.username,
        current_user.tenant_id,
        file_hash,
        filename,
    )
    grant_dataset_access(current_user.username, dataset_id, granted_by_username=current_user.username)
    register_dataset_hash(dataset_id, file_hash)
    logger.info(
        "User '%s' uploaded document dataset '%s' from file '%s'",
        current_user.username,
        dataset_id,
        filename,
    )
    extension = os.path.splitext(filename.lower())[1]
    return {
        "message": "File stored",
        "dataset_id": dataset_id,
        "tenant_id": current_user.tenant_id,
        "filename": filename,
        "rows": parsed_document.metadata.get("rows"),
        "columns": None,
        "reused": False,
        "indexing": "pending" if extension != ".csv" else "queued",
    }


def list_visible_datasets(current_user: User) -> dict:
    datasets = list_dataset_records(current_user)

    filtered_datasets = []
    for dataset in datasets:
        if dataset_exists(dataset["id"], dataset.get("file")):
            filtered_datasets.append(dataset)

    if not filtered_datasets and datasets:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dataset metadata exists but backing files are missing.",
        )

    logger.info("User '%s' listed %s datasets", current_user.username, len(filtered_datasets))
    return {
        "count": len(filtered_datasets),
        "datasets": filtered_datasets,
    }
