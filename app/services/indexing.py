import logging

from app.services.ingestion.chunking import build_chunks
from app.services.ingestion.pipeline import parse_stored_document
from app.services.rag import add_documents, remove_dataset_documents
from app.services.storage import read_dataset_bytes, read_dataset_file_bytes

logger = logging.getLogger(__name__)


def index_dataset_file(dataset_id: str, file_name: str) -> None:
    try:
        try:
            raw_bytes = read_dataset_file_bytes(dataset_id, file_name)
        except Exception:
            raw_bytes = read_dataset_bytes(dataset_id)

        document = parse_stored_document(filename=file_name, content=raw_bytes)
        chunks = build_chunks(document)
        if not chunks:
            logger.warning("No indexable chunks were produced for dataset '%s' file '%s'", dataset_id, file_name)
            return

        remove_dataset_documents(dataset_id)
        add_documents(
            texts=[chunk.text for chunk in chunks],
            ids=[f"{dataset_id}:{chunk.chunk_id}" for chunk in chunks],
            metadatas=[
                {
                    "dataset_id": dataset_id,
                    "file_name": file_name,
                    "chunk_index": chunk.chunk_index,
                    **chunk.metadata,
                }
                for chunk in chunks
            ],
        )
        logger.info("Indexed dataset '%s' for RAG with %s chunks", dataset_id, len(chunks))
    except Exception:
        logger.exception("Dataset indexing failed for dataset '%s'", dataset_id)
