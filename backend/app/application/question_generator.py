"""AI question generator.

For each chunk of a document we ask the model to write a small set of questions
grounded ONLY in that passage, returned as strict JSON. Because we generate per
chunk, every question inherits that chunk's source location (slide/page) for
free — no separate citation step needed.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from ..domain.document import ParsedDocument
from ..domain.question import Difficulty, Question, QuestionType
from ..infrastructure.ai import AIError, AIProvider, QuotaExceededError
from .chunking import Chunk, chunk_document

logger = logging.getLogger(__name__)


@dataclass
class GenerationBatch:
    questions: list[Question] = field(default_factory=list)
    quota_exceeded: bool = False

DEFAULT_TYPES: tuple[QuestionType, ...] = (
    QuestionType.MULTIPLE_CHOICE,
    QuestionType.TRUE_FALSE,
    QuestionType.FILL_BLANK,
    QuestionType.SHORT_ANSWER,
    QuestionType.FLASHCARD,
    QuestionType.MATCHING,
    QuestionType.ORDERING,
    QuestionType.SCENARIO,
    QuestionType.CASE_STUDY,
    QuestionType.TRICK,
)

_SYSTEM = (
    "You are an expert exam writer. You create study questions grounded STRICTLY "
    "in the passage you are given. Never introduce facts not present in the passage. "
    "Always respond with valid JSON only — no markdown, no commentary."
)

_TYPE_GUIDE = """\
Question type formats (JSON fields per item):
- multiple_choice: {"type","question","options":[4 strings],"answer":<exact correct option text>,"explanation","difficulty","topic"}
- true_false: {"type","question","answer":"True" or "False","explanation","difficulty","topic"}
- fill_blank: {"type","question":<sentence with "____">,"answer":<missing text>,"explanation","difficulty","topic"}
- short_answer: {"type","question","answer":<concise model answer>,"explanation","difficulty","topic"}
- flashcard: {"type":"flashcard","question":<front/term>,"answer":<back/definition>,"explanation","difficulty","topic"}
- matching: {"type","question","pairs":[{"left","right"}, ...],"explanation","difficulty","topic"}
- ordering: {"type","question","correct_order":[step1, step2, ...],"explanation","difficulty","topic"}
- scenario / case_study: {"type","question":<scenario + question>,"answer":<model answer>,"explanation","difficulty","topic"}
- trick: {"type":"trick","question","options":[4 strings],"answer":<correct option>,"explanation":<why the tempting wrong answer is wrong>,"difficulty","topic"}
difficulty must be one of: easy, medium, hard.
"""


class QuestionGenerator:
    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    def generate_for_document(
        self,
        doc: ParsedDocument,
        document_id: int,
        *,
        types: tuple[QuestionType, ...] = DEFAULT_TYPES,
        per_chunk: int = 3,
        max_questions: int = 30,
        max_chunks: int | None = None,
    ) -> GenerationBatch:
        chunks = chunk_document(doc)
        if max_chunks is not None:
            chunks = chunks[:max_chunks]

        results: list[Question] = []
        seen: set[str] = set()
        cycle = list(types)
        offset = 0
        for chunk in chunks:
            if len(results) >= max_questions:
                break
            # Rotate through the type list so every type gets requested across
            # the document, instead of letting the model default to easy ones.
            targets = tuple(cycle[(offset + j) % len(cycle)] for j in range(per_chunk))
            offset += per_chunk
            try:
                generated = self._generate_for_chunk(chunk.text, targets, per_chunk)
            except QuotaExceededError as exc:
                # A hard quota cap won't clear up mid-run — stop immediately
                # instead of burning a retry-with-backoff on every remaining
                # chunk for calls that are guaranteed to fail the same way.
                logger.warning("Stopping generation early: %s", exc)
                return GenerationBatch(questions=results, quota_exceeded=True)
            except AIError as exc:
                logger.warning("Question generation failed for a chunk: %s", exc)
                continue

            for q in generated:
                q.document_id = document_id
                q.source_title = doc.title
                q.source_location = _location_str(chunk)
                key = q.normalized_key()
                if key and key not in seen and q.is_valid:
                    seen.add(key)
                    results.append(q)
                    if len(results) >= max_questions:
                        break
        logger.info("Generated %d questions for document %s", len(results), document_id)
        return GenerationBatch(questions=results)

    def _generate_for_chunk(
        self, text: str, types: tuple[QuestionType, ...], count: int
    ) -> list[Question]:
        type_list = ", ".join(t.value for t in types)
        prompt = (
            f"{_TYPE_GUIDE}\n"
            f"Write exactly {count} study questions using ONLY the passage below. "
            f"Produce one question of EACH of these types, in this order: {type_list}. "
            "Only substitute a different type for one that genuinely cannot be formed "
            "from this passage (e.g. ordering needs a sequence, matching needs pairs). "
            'Return JSON: {"questions": [ ...items... ]}.\n\n'
            f"PASSAGE:\n{text}"
        )
        raw = self._provider.generate(prompt, system=_SYSTEM, temperature=0.5, json_mode=True)
        return _parse_questions(raw)


# --------------------------------------------------------------------------- #
# Parsing / normalization
# --------------------------------------------------------------------------- #
def _parse_questions(raw: str) -> list[Question]:
    data = _loads_lenient(raw)
    if data is None:
        return []
    items = data.get("questions") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    out: list[Question] = []
    for item in items:
        if isinstance(item, dict):
            q = _normalize_item(item)
            if q is not None:
                out.append(q)
    return out


def _loads_lenient(raw: str) -> dict | list | None:
    raw = raw.strip()
    if raw.startswith("```"):  # strip accidental code fences
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fall back to the first {...} or [...] block.
        for opener, closer in (("{", "}"), ("[", "]")):
            start, end = raw.find(opener), raw.rfind(closer)
            if start != -1 and end > start:
                try:
                    return json.loads(raw[start : end + 1])
                except json.JSONDecodeError:
                    continue
    return None


def _normalize_item(item: dict) -> Question | None:
    qtype = QuestionType.coerce(str(item.get("type", "")))
    if qtype is None:
        return None
    prompt = str(item.get("question", "")).strip()
    if not prompt:
        return None

    options = [str(o) for o in item.get("options", []) if str(o).strip()]
    answer_data: dict = {}
    answer = str(item.get("answer", "")).strip()

    if qtype == QuestionType.TRUE_FALSE:
        options = ["True", "False"]
        answer = "True" if answer.lower().startswith("t") else "False"
    elif qtype == QuestionType.MATCHING:
        pairs = [
            {"left": str(p.get("left", "")), "right": str(p.get("right", ""))}
            for p in item.get("pairs", [])
            if isinstance(p, dict)
        ]
        if len(pairs) < 2:
            return None
        answer_data = {"pairs": pairs}
        answer = "; ".join(f"{p['left']} = {p['right']}" for p in pairs)
    elif qtype == QuestionType.ORDERING:
        order = [str(s) for s in item.get("correct_order", []) if str(s).strip()]
        if len(order) < 2:
            return None
        answer_data = {"correct_order": order}
        options = list(order)  # the UI will shuffle these
        answer = " -> ".join(order)
    elif qtype in (QuestionType.MULTIPLE_CHOICE, QuestionType.TRICK):
        if len(options) < 2 or not answer:
            return None
        if answer in options:
            answer_data = {"correct_index": options.index(answer)}

    if not answer:
        return None

    return Question(
        question_type=qtype,
        prompt=prompt,
        answer=answer,
        explanation=str(item.get("explanation", "")).strip(),
        difficulty=Difficulty.coerce(str(item.get("difficulty", ""))),
        topic=str(item.get("topic", "")).strip(),
        options=options,
        answer_data=answer_data,
    )


def _location_str(chunk: Chunk) -> str:
    if chunk.slide is not None:
        return f"slide {chunk.slide}"
    if chunk.page is not None:
        return f"page {chunk.page}"
    return ""
