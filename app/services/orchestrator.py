import logging
import time
from io import BytesIO

import pandas as pd
from fastapi import HTTPException, status

from app.core.auth import User
from app.services.access import ensure_dataset_access
from app.services.audit import record_audit_event
from app.services.guardrails import validate_question
from app.services.llm import ask_llm
from app.services.rag import query_documents
from app.services.storage import dataset_exists, read_dataset_bytes

logger = logging.getLogger(__name__)


def _detect_mode(question: str) -> str:
    lowered_question = question.lower()
    if "why" in lowered_question:
        return "analysis"
    if "trend" in lowered_question:
        return "trend"
    if "summary" in lowered_question or "what" in lowered_question:
        return "summary"
    return "general"


def _build_trend_info(dataframe: pd.DataFrame) -> str:
    if "revenue" not in dataframe.columns:
        return "Revenue column not available."

    revenue = dataframe["revenue"]
    if len(revenue) <= 1:
        return "Not enough revenue data to calculate trend."

    change = revenue.iloc[-1] - revenue.iloc[0]
    percent_change = (change / revenue.iloc[0]) * 100 if revenue.iloc[0] != 0 else 0
    return (
        f"Revenue started at {revenue.iloc[0]} and ended at {revenue.iloc[-1]}. "
        f"Change: {change} ({percent_change:.2f}%)."
    )


def _build_anomaly_info(dataframe: pd.DataFrame) -> str:
    if "revenue" not in dataframe.columns:
        return "Revenue column not available for anomaly detection."

    revenue = dataframe["revenue"]
    if len(revenue) <= 2:
        return "Not enough revenue data for anomaly detection."

    mean = revenue.mean()
    std = revenue.std()
    anomalies = revenue[abs(revenue - mean) > 2 * std]
    if anomalies.empty:
        return "No significant anomalies detected."

    return f"Detected anomalies at values: {list(anomalies.values)}"


def _build_dataset_snapshot(dataframe: pd.DataFrame) -> str:
    numeric_columns = list(dataframe.select_dtypes(include="number").columns)
    categorical_columns = [
        str(column)
        for column in dataframe.columns
        if column not in numeric_columns
    ]

    numeric_summary = "No numeric columns detected."
    if numeric_columns:
        numeric_summary = dataframe[numeric_columns[:8]].describe().round(2).to_string()

    sample_rows = dataframe.head(5).to_csv(index=False)
    return "\n".join(
        [
            f"Rows: {len(dataframe)}",
            f"Columns: {', '.join(str(column) for column in dataframe.columns)}",
            f"Numeric columns: {', '.join(str(column) for column in numeric_columns[:8]) or 'None'}",
            f"Categorical columns: {', '.join(categorical_columns[:8]) or 'None'}",
            "Numeric summary:",
            numeric_summary,
            "Sample rows:",
            sample_rows,
        ]
    )


def _build_local_fallback_answer(
    question: str,
    mode: str,
    dataframe: pd.DataFrame,
    trend_info: str,
    anomaly_info: str,
    rag_context: str,
) -> str:
    columns = ", ".join(str(column) for column in dataframe.columns[:8])
    row_count = len(dataframe)
    parts = [
        "Local fallback analysis was used because the remote LLM was unavailable.",
        "",
        f"Question: {question}",
        f"Mode: {mode}",
        f"Dataset size: {row_count} rows",
        f"Visible columns: {columns or 'No columns detected'}",
        f"Trend summary: {trend_info}",
        f"Anomaly summary: {anomaly_info}",
    ]

    if rag_context != "No relevant documents found.":
        parts.append(f"Retrieved context: {rag_context}")

    parts.append("This result is suitable for demos and operational fallback, but it is less expressive than the live LLM response.")
    return "\n".join(parts)


def _build_general_fallback_answer(question: str) -> str:
    return "\n".join(
        [
            "Local fallback response was used because the remote LLM was unavailable.",
            "",
            f"Question: {question}",
            "This general copilot mode is intended for operational guidance, platform walkthroughs, and non-dataset questions.",
            "For the strongest answer quality, enable live LLM connectivity or add a local model provider such as Ollama later.",
        ]
    )


def answer_question(question: str, dataset_id: str, current_user: User) -> dict:
    overall_start = time.perf_counter()
    cleaned_question = validate_question(question)
    cleaned_dataset_id = dataset_id.strip()
    ensure_dataset_access(cleaned_dataset_id, current_user)

    if not dataset_exists(cleaned_dataset_id):
        logger.warning("Dataset '%s' not found for user '%s'", cleaned_dataset_id, current_user.username)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Dataset not found", "dataset_id": cleaned_dataset_id},
        )

    dataframe = pd.read_csv(BytesIO(read_dataset_bytes(cleaned_dataset_id)))
    mode = _detect_mode(cleaned_question)
    dataset_snapshot = _build_dataset_snapshot(dataframe)
    trend_info = _build_trend_info(dataframe)
    anomaly_info = _build_anomaly_info(dataframe)

    rag_start = time.perf_counter()
    rag_results = query_documents(cleaned_question, dataset_id=cleaned_dataset_id)
    rag_duration_ms = round((time.perf_counter() - rag_start) * 1000, 2)
    
    rag_context = "No relevant documents found."
    if rag_results and isinstance(rag_results, list) and len(rag_results) > 0 and rag_results[0]:
        rag_context = "\n".join([str(doc) for doc in rag_results[0]])

    prompt = f"""
    You are a business analyst for an AI Ops Copilot.

    MODE: {mode}

    DATA SNAPSHOT:
    {dataset_snapshot}

    TREND:
    {trend_info}

    ANOMALY DETECTION:
    {anomaly_info}

    CONTEXT:
    {rag_context}

    QUESTION:
    {cleaned_question}

    Instructions:
    - Give a concise, evidence-based answer.
    - If anomalies exist, explain possible causes.
    - If a trend exists, explain direction and impact.
    - Use context only when it is relevant to the question.
    """

    print(f"Orchestrator running in mode: {mode}")
    logger.info(
        "User '%s' asked question against dataset '%s' in mode '%s'",
        current_user.username,
        cleaned_dataset_id,
        mode,
    )

    llm_start = time.perf_counter()
    answer_source = "llm"
    try:
        answer = ask_llm(prompt)
    except Exception:
        logger.exception("LLM call failed; returning fallback analysis.")
        answer = _build_local_fallback_answer(
            cleaned_question,
            mode,
            dataframe,
            trend_info,
            anomaly_info,
            rag_context,
        )
        answer_source = "local_fallback"
    llm_duration_ms = round((time.perf_counter() - llm_start) * 1000, 2)
    total_duration_ms = round((time.perf_counter() - overall_start) * 1000, 2)

    print(
        f"Latency | total={total_duration_ms}ms rag={rag_duration_ms}ms llm={llm_duration_ms}ms"
    )
    logger.info(
        "Latency measured dataset='%s' total_ms=%s rag_ms=%s llm_ms=%s",
        cleaned_dataset_id,
        total_duration_ms,
        rag_duration_ms,
        llm_duration_ms,
    )

    record_audit_event(
        event_type="query.ask",
        actor_username=current_user.username,
        tenant_id=current_user.tenant_id,
        resource_type="dataset",
        resource_id=cleaned_dataset_id,
        detail=f"Question executed in mode '{mode}' total_ms={total_duration_ms}.",
    )
    return {
        "question": cleaned_question,
        "dataset_id": cleaned_dataset_id,
        "tenant_id": current_user.tenant_id,
        "requested_by": current_user.username,
        "mode": mode,
        "answer_source": answer_source,
        "rag_used": rag_context != "No relevant documents found.",
        "latency_ms": {
            "total": total_duration_ms,
            "rag": rag_duration_ms,
            "llm": llm_duration_ms,
        },
        "answer": answer,
    }


def answer_general_question(question: str, current_user: User) -> dict:
    overall_start = time.perf_counter()
    cleaned_question = validate_question(question)
    mode = "general"

    prompt = f"""
    You are an AI Ops Copilot for operations, platform, and data users.

    MODE: {mode}

    QUESTION:
    {cleaned_question}

    Instructions:
    - Answer clearly and directly.
    - Focus on operational usefulness.
    - If the question is broad, give a concise practical answer first.
    - If a dataset is required to answer accurately, say so explicitly.
    """

    logger.info("User '%s' asked a general copilot question", current_user.username)

    rag_duration_ms = 0.0
    llm_start = time.perf_counter()
    answer_source = "llm"
    try:
        answer = ask_llm(prompt)
    except Exception:
        logger.exception("General LLM call failed; returning fallback response.")
        answer = _build_general_fallback_answer(cleaned_question)
        answer_source = "local_fallback"
    llm_duration_ms = round((time.perf_counter() - llm_start) * 1000, 2)
    total_duration_ms = round((time.perf_counter() - overall_start) * 1000, 2)

    record_audit_event(
        event_type="query.general",
        actor_username=current_user.username,
        tenant_id=current_user.tenant_id,
        resource_type="copilot",
        resource_id="general",
        detail=f"General question executed total_ms={total_duration_ms}.",
    )
    return {
        "question": cleaned_question,
        "dataset_id": None,
        "tenant_id": current_user.tenant_id,
        "requested_by": current_user.username,
        "mode": mode,
        "answer_source": answer_source,
        "rag_used": False,
        "latency_ms": {
            "total": total_duration_ms,
            "rag": rag_duration_ms,
            "llm": llm_duration_ms,
        },
        "answer": answer,
    }
