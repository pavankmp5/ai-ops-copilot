from __future__ import annotations

import logging
import os
import re
from io import BytesIO

from app.core.settings import get_settings


def _dataset_filename(dataset_id: str) -> str:
    return f"{dataset_id}.csv"


def _dataset_blob_name(dataset_id: str) -> str:
    return f"datasets/{_dataset_filename(dataset_id)}"


def _sanitize_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", filename.strip())
    return cleaned or "document.bin"


def _dataset_storage_filename(dataset_id: str, filename: str) -> str:
    return f"{dataset_id}__{_sanitize_filename(filename)}"


def _dataset_storage_blob_name(dataset_id: str, filename: str) -> str:
    return f"datasets/{_dataset_storage_filename(dataset_id, filename)}"


_blob_container_client = None
logger = logging.getLogger(__name__)


def _get_blob_client():
    global _blob_container_client
    if _blob_container_client is not None:
        return _blob_container_client

    settings = get_settings()
    if settings.storage_provider != "azure_blob":
        raise RuntimeError("Azure Blob storage is not enabled.")
    if not settings.azure_blob_connection_string or not settings.azure_blob_container:
        raise RuntimeError("Azure Blob storage is not configured.")

    from azure.storage.blob import BlobServiceClient

    service = BlobServiceClient.from_connection_string(settings.azure_blob_connection_string)
    container = service.get_container_client(settings.azure_blob_container)
    try:
        container.create_container()
    except Exception:
        pass
    _blob_container_client = container
    return _blob_container_client


def dataset_exists(dataset_id: str, file_name: str | None = None) -> bool:
    settings = get_settings()
    if settings.storage_provider == "azure_blob":
        try:
            blob_client = _get_blob_client()
            if file_name:
                return blob_client.get_blob_client(_dataset_storage_blob_name(dataset_id, file_name)).exists()
            if blob_client.get_blob_client(_dataset_blob_name(dataset_id)).exists():
                return True
            for _ in blob_client.list_blobs(name_starts_with=f"datasets/{dataset_id}__", results_per_page=1):
                return True
            return False
        except Exception:
            return False

    if file_name and os.path.exists(dataset_file_path(dataset_id, file_name)):
        return True
    if os.path.exists(dataset_local_path(dataset_id)):
        return True
    try:
        for candidate in os.listdir(settings.data_dir):
            if candidate.startswith(f"{dataset_id}__"):
                return True
    except Exception:
        return False
    return False


def dataset_local_path(dataset_id: str) -> str:
    settings = get_settings()
    return os.path.join(settings.data_dir, _dataset_filename(dataset_id))


def dataset_file_path(dataset_id: str, file_name: str) -> str:
    settings = get_settings()
    return os.path.join(settings.data_dir, _dataset_storage_filename(dataset_id, file_name))


def save_dataset_csv(dataset_id: str, csv_bytes: bytes) -> None:
    settings = get_settings()
    if settings.storage_provider == "azure_blob":
        blob = _get_blob_client().get_blob_client(_dataset_blob_name(dataset_id))
        blob.upload_blob(csv_bytes, overwrite=True, content_type="text/csv")
        return

    os.makedirs(settings.data_dir, exist_ok=True)
    with open(dataset_local_path(dataset_id), "wb") as file_handle:
        file_handle.write(csv_bytes)


def save_dataset_file(dataset_id: str, file_name: str, file_bytes: bytes, content_type: str | None = None) -> None:
    settings = get_settings()
    if settings.storage_provider == "azure_blob":
        blob = _get_blob_client().get_blob_client(_dataset_storage_blob_name(dataset_id, file_name))
        blob.upload_blob(file_bytes, overwrite=True, content_type=content_type or "application/octet-stream")
        return

    os.makedirs(settings.data_dir, exist_ok=True)
    with open(dataset_file_path(dataset_id, file_name), "wb") as file_handle:
        file_handle.write(file_bytes)


def read_dataset_bytes(dataset_id: str) -> bytes:
    settings = get_settings()
    if settings.storage_provider == "azure_blob":
        blob = _get_blob_client().get_blob_client(_dataset_blob_name(dataset_id))
        return blob.download_blob().readall()

    with open(dataset_local_path(dataset_id), "rb") as file_handle:
        return file_handle.read()


def read_dataset_file_bytes(dataset_id: str, file_name: str) -> bytes:
    settings = get_settings()
    if settings.storage_provider == "azure_blob":
        blob = _get_blob_client().get_blob_client(_dataset_storage_blob_name(dataset_id, file_name))
        return blob.download_blob().readall()

    with open(dataset_file_path(dataset_id, file_name), "rb") as file_handle:
        return file_handle.read()


def dataset_readable_stream(dataset_id: str) -> BytesIO:
    return BytesIO(read_dataset_bytes(dataset_id))


def storage_health() -> dict:
    settings = get_settings()
    if settings.storage_provider == "azure_blob":
        try:
            _get_blob_client().list_blobs(name_starts_with="datasets/", results_per_page=1)
            return {"provider": "azure_blob", "available": True}
        except Exception:
            logger.exception("Azure Blob storage readiness probe failed.")
            return {"provider": "azure_blob", "available": False}

    # For local storage, validate that we can create and write in the target directory.
    probe_file = os.path.join(settings.data_dir, ".healthcheck_write_probe")
    try:
        os.makedirs(settings.data_dir, exist_ok=True)
        with open(probe_file, "wb") as file_handle:
            file_handle.write(b"ok")
        os.remove(probe_file)
        return {"provider": "local", "available": True}
    except Exception:
        if os.path.exists(probe_file):
            try:
                os.remove(probe_file)
            except Exception:
                pass
        return {"provider": "local", "available": False}
