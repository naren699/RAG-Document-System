from pydantic import BaseModel


class TestQuestion(BaseModel):
    question_id: str
    question: str
    document_id: str
    gold_answer: str | None = None
    answerable: bool
    gold_chunk_ids: list[str] = []
    answer_type: str
    category: str
    expected_behavior: str = ""


class SystemAnswer(BaseModel):
    answer_id: str
    run_id: str
    question_id: str
    question: str
    answer_text: str
    is_refusal: bool
    retrieved_chunk_ids: list[str]
    retrieved_chunks: list[dict]
    latency_ms: int
    tokens_used: dict
    grounding: dict
    model: str
    provider: str


class RunMetadata(BaseModel):
    run_id: str
    status: str  # running, completed, failed
    timestamp: str
    model: str
    provider: str
    retrieval_method: str
    k: int
    score_threshold: float | None = None
    dataset: str
    total_questions: int
    completed_questions: int = 0
    error: str | None = None
