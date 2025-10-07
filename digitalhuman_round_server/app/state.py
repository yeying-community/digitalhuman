from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime, timezone

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class QAPair:
    question_index: int
    question: str
    category: Optional[str]
    qa_id: str
    answer: Optional[str] = None
    answered_at: Optional[str] = None
    answer_length: Optional[int] = None

@dataclass
class RoundState:
    session_id: str
    round_index: int
    round_id: Optional[str]
    round_type: str
    session_name: Optional[str]
    room_id: Optional[str]

    questions: List[str]
    categories: List[Optional[str]]
    total_questions: int
    current_index: int = 0
    qa_pairs: List[QAPair] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)

    @classmethod
    def create(cls, session_id: str, round_index: int, round_id: Optional[str],
               round_type: str, session_name: Optional[str], room_id: Optional[str],
               questions: List[str], categories: List[Optional[str]]) -> "RoundState":
        qa_pairs: List[QAPair] = []
        for i, q in enumerate(questions):
            qa_pairs.append(QAPair(
                question_index=i,
                question=q,
                category=(categories[i] if i < len(categories) else None),
                qa_id=str(uuid4()),
            ))
        return cls(
            session_id=session_id,
            round_index=round_index,
            round_id=round_id,
            round_type=round_type,
            session_name=session_name,
            room_id=room_id,
            questions=questions,
            categories=categories,
            total_questions=len(questions),
            qa_pairs=qa_pairs,
        )

    def is_completed(self) -> bool:
        return self.current_index >= self.total_questions

    def current_question_payload(self):
        if self.is_completed():
            return None
        q = self.qa_pairs[self.current_index]
        return {
            "question": q.question,
            "category": q.category,
            "question_number": self.current_index + 1,
            "total_questions": self.total_questions,
        }

    def save_answer(self, question_index: int, answer_text: str) -> Dict[str, Any]:
        if self.is_completed():
            raise ValueError("Round already completed.")
        if question_index != self.current_index:
            raise ValueError(f"Out-of-order answer: expected {self.current_index}, got {question_index}")
        qa = self.qa_pairs[self.current_index]
        qa.answer = (answer_text or "").strip()
        qa.answered_at = now_iso()
        qa.answer_length = len(qa.answer)
        self.current_index += 1
        return {
            "qa_id": qa.qa_id,
            "question_index": qa.question_index,
            "answered_at": qa.answered_at,
            "is_round_completed": self.is_completed(),
        }

    def build_qa_complete(self) -> Dict[str, Any]:
        if not self.is_completed():
            raise RuntimeError("Cannot build qa_complete before finishing all answers.")
        return {
            "round_info": {
                "round_id": self.round_id,
                "session_id": self.session_id,
                "round_index": self.round_index,
                "total_questions": self.total_questions,
                "completed_at": now_iso(),
                "round_type": self.round_type,
            },
            "session_info": {
                "session_name": self.session_name,
                "room_id": self.room_id,
            },
            "qa_pairs": [
                {
                    "question_index": qa.question_index,
                    "category": qa.category,
                    "question": qa.question,
                    "answer": qa.answer,
                    "answered_at": qa.answered_at,
                    "answer_length": qa.answer_length,
                    "qa_id": qa.qa_id,
                } for qa in self.qa_pairs
            ],
            "analysis_ready": True,
            "metadata": {},
        }
