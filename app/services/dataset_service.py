import hashlib
import logging
import uuid
from io import BytesIO

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
from app.services.guardrails import validate_csv_upload
from app.services.storage import dataset_exists, save_dataset_csv

logger = logging.getLogger(__name__)


async def upload_dataset(file: UploadFile, current_user: User) -> dict:
    file_bytes, dataframe = await validate_csv_upload(file)
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
            print("Dataset upload deduplicated and reused")
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
        normalized_csv_bytes = dataframe.to_csv(index=False).encode("utf-8")
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
            "rows": len(dataframe),
            "columns": list(dataframe.columns),
            "reused": False,
            "indexing": "pending",
        }

    dataset_id = str(uuid.uuid4())
    normalized_csv_bytes = dataframe.to_csv(index=False).encode("utf-8")
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

    print("Dataset stored successfully")
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
        "rows": len(dataframe),
        "columns": list(dataframe.columns),
        "indexing": "pending",
    }


def list_visible_datasets(current_user: User) -> dict:
    datasets = list_dataset_records(current_user)

    filtered_datasets = []
    for dataset in datasets:
        if dataset_exists(dataset["id"]):
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
