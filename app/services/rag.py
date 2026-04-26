import logging
from functools import lru_cache

from app.core.settings import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def _get_collection():
    settings = get_settings()
    if not settings.rag_enabled:
        raise RuntimeError("RAG is disabled.")

    try:
        import chromadb
    except ImportError as exc:
        logger.warning("ChromaDB is not installed; RAG storage is unavailable.")
        raise RuntimeError("ChromaDB is not installed.") from exc

    client = chromadb.PersistentClient(path=settings.vector_db_dir)
    return client.get_or_create_collection(name=settings.rag_collection_name)


@lru_cache
def _get_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        logger.warning("sentence-transformers is not installed; embeddings are unavailable.")
        raise RuntimeError("sentence-transformers is not installed.") from exc

    print("Loading embedding model for RAG")
    logger.info("Loading sentence transformer model")
    try:
        return SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
    except Exception as exc:
        logger.warning("Sentence transformer model is not cached locally; skipping RAG.")
        raise RuntimeError("Sentence transformer model is not cached locally.") from exc


def add_documents(texts, ids=None, metadatas=None):
    try:
        model = _get_model()
        collection = _get_collection()
    except RuntimeError:
        logger.info("Skipping document indexing because the optional RAG stack is unavailable.")
        return

    embeddings = model.encode(texts).tolist()
    resolved_ids = ids or [str(i) for i in range(len(texts))]
    resolved_metadatas = metadatas or [{} for _ in texts]

    collection.upsert(
        documents=texts,
        embeddings=embeddings,
        ids=resolved_ids,
        metadatas=resolved_metadatas,
    )


def remove_dataset_documents(dataset_id: str) -> None:
    try:
        collection = _get_collection()
    except RuntimeError:
        return

    try:
        collection.delete(where={"dataset_id": dataset_id})
    except Exception:
        logger.exception("Failed to remove RAG documents for dataset '%s'", dataset_id)


def query_documents(query, dataset_id: str | None = None):
    try:
        collection = _get_collection()
    except RuntimeError:
        logger.info("Returning empty RAG results because the optional RAG stack is unavailable.")
        return []

    if collection.count() == 0:
        logger.info("RAG collection is empty; skipping embedding lookup.")
        return []

    try:
        model = _get_model()
    except RuntimeError:
        logger.info("Returning empty RAG results because the optional RAG stack is unavailable.")
        return []

    query_embedding = model.encode([query]).tolist()
    settings = get_settings()

    query_kwargs = {
        "query_embeddings": query_embedding,
        "n_results": settings.rag_top_k,
    }
    if dataset_id:
        query_kwargs["where"] = {"dataset_id": dataset_id}

    results = collection.query(**query_kwargs)

    return results["documents"]
