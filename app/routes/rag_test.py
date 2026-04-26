from fastapi import APIRouter
from app.services.rag import add_documents, query_documents

router = APIRouter()

@router.get("/test-rag")
def test_rag():
    add_documents([
        "Revenue dropped due to low user engagement",
        "Customers complained about pricing increase"
    ])

    results = query_documents("Why did revenue drop?")

    return {"results": results}