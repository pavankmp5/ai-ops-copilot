from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile
from pydantic import BaseModel

from app.core.auth import User, authorize, get_current_user
from app.services.dataset_service import list_visible_datasets, upload_dataset, upload_document
from app.services.indexing import index_dataset_file
from app.services.access import share_dataset

router = APIRouter(tags=["datasets"])


class ShareDatasetRequest(BaseModel):
    target_username: str


class UploadDatasetResponse(BaseModel):
    message: str
    dataset_id: str
    tenant_id: str | None = None
    filename: str | None = None
    rows: int | None = None
    columns: list[str] | None = None
    reused: bool = False
    indexing: str


class DatasetRecordResponse(BaseModel):
    id: str
    tenant_id: str
    file: str
    owner_username: str
    created_at: str


class DatasetListResponse(BaseModel):
    count: int
    datasets: list[DatasetRecordResponse]


@router.post("/upload-csv", response_model=UploadDatasetResponse)
async def upload_csv(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    authorize("datasets.upload", current_user)
    result = await upload_dataset(file, current_user)
    if not result.get("reused"):
        background_tasks.add_task(
            index_dataset_file,
            result["dataset_id"],
            result.get("filename") or f"{result['dataset_id']}.csv",
        )
        result["indexing"] = "queued"
    else:
        result["indexing"] = "existing"
    return result


@router.post("/upload-document", response_model=UploadDatasetResponse)
async def upload_document_route(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    authorize("datasets.upload", current_user)
    result = await upload_document(file, current_user)
    if not result.get("reused"):
        background_tasks.add_task(
            index_dataset_file,
            result["dataset_id"],
            result.get("filename") or f"{result['dataset_id']}.txt",
        )
        result["indexing"] = "queued"
    else:
        result["indexing"] = "existing"
    return result


@router.get("/datasets", response_model=DatasetListResponse)
def list_datasets(current_user: User = Depends(get_current_user)):
    return list_visible_datasets(current_user)


@router.post("/datasets/{dataset_id}/share")
def share_dataset_route(
    dataset_id: str,
    request: ShareDatasetRequest,
    current_user: User = Depends(get_current_user),
):
    authorize("datasets.share", current_user)
    return share_dataset(dataset_id, request.target_username.strip(), current_user)
