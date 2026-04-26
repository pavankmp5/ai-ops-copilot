import logging
from io import BytesIO

import pandas as pd

from app.services.rag import add_documents, remove_dataset_documents
from app.services.storage import read_dataset_bytes

logger = logging.getLogger(__name__)


def _build_dataset_documents(dataset_id: str, file_name: str, dataframe: pd.DataFrame) -> list[dict]:
    preview_rows = dataframe.head(10).to_csv(index=False)
    columns = ", ".join(str(column) for column in dataframe.columns)
    numeric_columns = list(dataframe.select_dtypes(include="number").columns)

    overview = "\n".join(
        [
            f"Dataset ID: {dataset_id}",
            f"Filename: {file_name}",
            f"Rows: {len(dataframe)}",
            f"Columns: {columns or 'No columns'}",
        ]
    )

    numeric_summary = "No numeric summary available."
    if numeric_columns:
        numeric_summary = dataframe[numeric_columns[:8]].describe().round(2).to_string()

    documents = [
        {
            "id": f"{dataset_id}:overview",
            "text": overview,
            "metadata": {"dataset_id": dataset_id, "file_name": file_name, "section": "overview"},
        },
        {
            "id": f"{dataset_id}:summary",
            "text": f"Numeric summary for dataset {file_name}\n{numeric_summary}",
            "metadata": {"dataset_id": dataset_id, "file_name": file_name, "section": "summary"},
        },
        {
            "id": f"{dataset_id}:preview",
            "text": f"Preview rows for dataset {file_name}\n{preview_rows}",
            "metadata": {"dataset_id": dataset_id, "file_name": file_name, "section": "preview"},
        },
    ]

    return documents


def index_dataset_file(dataset_id: str, file_name: str) -> None:
    try:
        dataframe = pd.read_csv(BytesIO(read_dataset_bytes(dataset_id)))
        documents = _build_dataset_documents(dataset_id, file_name, dataframe)
        remove_dataset_documents(dataset_id)
        add_documents(
            texts=[document["text"] for document in documents],
            ids=[document["id"] for document in documents],
            metadatas=[document["metadata"] for document in documents],
        )
        logger.info("Indexed dataset '%s' for RAG with %s documents", dataset_id, len(documents))
    except Exception:
        logger.exception("Dataset indexing failed for dataset '%s'", dataset_id)
