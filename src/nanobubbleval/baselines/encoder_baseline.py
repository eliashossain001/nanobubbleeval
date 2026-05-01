"""B2: encoder QA-span baseline.

Uses a pre-trained biomedical extractive-QA model (default:
``ktrapeznikov/biobert_v1.1_pubmed_squad_v2``) prompted with one
natural-language question per headline field. The model returns the
highest-scoring answer span; spans below a calibrated confidence threshold
map to ``NOT_REPORTED``. SQuAD-v2's built-in unanswerable mechanism gives
the model a first-class abstain action that aligns with our NR convention.

For numeric fields, the predicted span is parsed by a small regex to
recover ``(value, unit)``. For text fields, the span is the value itself.

The implementation calls ``AutoModelForQuestionAnswering`` directly rather
than the high-level ``transformers.pipeline`` because Transformers 5.x
removed the standalone ``question-answering`` pipeline.

Usage:
    >>> bl = EncoderQABaseline()
    >>> preds = bl.predict_record("r1", "Lipid nanobubbles 200 nm in diameter ...")
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Mapping, Optional

from nanobubbleval.baselines.base import Baseline, FieldPrediction
from nanobubbleval.schema import HEADLINE_FIELDS, NR, NUMERIC_FIELDS, UnitNormalizer

LOG = logging.getLogger(__name__)

DEFAULT_MODEL = "ktrapeznikov/biobert_v1.1_pubmed_squad_v2"

QUESTIONS = {
    "size": "What is the particle or bubble size in nanometres?",
    "zeta_potential": "What is the zeta potential in millivolts?",
    "stability": "How long are the particles stable for?",
    "payload": "What drug, dye, gene, gas, or cargo is loaded?",
    "loading_efficiency": "What is the loading or encapsulation efficiency?",
    "release_profile": "What is the release profile or release behaviour?",
}


# Number followed by an optional space and a known unit token.
# The trailing word-boundary is applied only to alphanumeric units; "%" and
# percent are matched without one. Order: longer alternatives first.
_NUMERIC_UNIT = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*"
    r"(\%|"
    r"(?:nanometers|nanometres|nanometer|nanometre|micrometer|micrometre|"
    r"micron|microns|millimeter|millimetre|hours|hour|days|day|weeks|week|"
    r"minutes|minute|seconds|second|months|month|years|year|percent|"
    r"nm|um|μm|mm|mV|V|hrs|hr|wk|min|sec|mo|yr|h|d|s)\b)",
    re.I,
)


def _parse_numeric_span(span: str, field: str, normalizer: UnitNormalizer) -> FieldPrediction:
    """Extract (value, unit) from a QA-returned span for a numeric field."""
    if not span or not span.strip():
        return FieldPrediction.nr()
    m = _NUMERIC_UNIT.search(span)
    if m:
        return FieldPrediction(
            value=m.group(1),
            unit=m.group(2),
            evidence_quote=span.strip(),
        )
    # Fall back: try to extract just a number (no unit found)
    num = normalizer.parse_number(span)
    if num is None:
        return FieldPrediction.nr()
    value = str(int(num)) if num == int(num) else f"{num:g}"
    return FieldPrediction(value=value, unit=NR, evidence_quote=span.strip())


def _parse_text_span(span: str) -> FieldPrediction:
    """Extract value from a QA-returned span for a text field."""
    if not span or not span.strip():
        return FieldPrediction.nr()
    return FieldPrediction(value=span.strip(), unit="", evidence_quote=span.strip())


@dataclass
class EncoderConfig:
    model_id: str = DEFAULT_MODEL
    confidence_threshold: float = 0.20
    max_answer_len: int = 64
    handle_impossible_answer: bool = True
    max_seq_len: int = 512


class EncoderQABaseline(Baseline):
    """Pre-trained biomedical extractive-QA baseline.

    Default model is ``ktrapeznikov/biobert_v1.1_pubmed_squad_v2``;
    pass ``EncoderConfig(model_id=...)`` to swap.
    """

    name = "biobert-squadv2"

    def __init__(
        self,
        config: Optional[EncoderConfig] = None,
        normalizer: Optional[UnitNormalizer] = None,
    ) -> None:
        self.config = config or EncoderConfig()
        if self.config.model_id != DEFAULT_MODEL:
            self.name = self.config.model_id.split("/")[-1].lower()
        self._normalizer = normalizer or UnitNormalizer()
        self._tokenizer = None
        self._model = None
        self._device = None

    # ----------------------------------------------------------------- load

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForQuestionAnswering, AutoTokenizer

        LOG.info("[%s] loading %s", self.name, self.config.model_id)
        self._tokenizer = AutoTokenizer.from_pretrained(self.config.model_id)
        self._model = AutoModelForQuestionAnswering.from_pretrained(self.config.model_id)
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = self._model.to(self._device)
        self._model.eval()
        LOG.info("[%s] model loaded on %s", self.name, self._device)

    # --------------------------------------------------------------- inference

    def _qa(self, question: str, context: str) -> tuple[str, float]:
        """Manual extractive-QA: returns ``(answer, score)``.

        SQuAD-v2 convention: index 0 is the ``[CLS]`` token; its
        start+end logit sum is the "no answer" score. If that exceeds the
        best span score and ``handle_impossible_answer`` is set, we return
        an empty answer.
        """
        import torch
        import torch.nn.functional as F

        enc = self._tokenizer(
            question, context,
            return_tensors="pt",
            truncation="only_second",
            max_length=self.config.max_seq_len,
            return_offsets_mapping=True,
        )
        offsets = enc.pop("offset_mapping")[0].tolist()
        sequence_ids = enc.sequence_ids(0)
        enc = {k: v.to(self._device) for k, v in enc.items()}
        with torch.no_grad():
            out = self._model(**enc)

        start_logits = out.start_logits[0]
        end_logits = out.end_logits[0]
        L = start_logits.shape[0]

        # No-answer score: logits at the [CLS] position
        null_score = float(start_logits[0] + end_logits[0])

        # Mask out positions outside the context (sequence_id != 1) and
        # special tokens (sequence_id is None).
        ctx_mask = [(sid == 1) for sid in sequence_ids]

        # Best span search (top-k start, top-k end, then check span)
        K = 20
        start_top = torch.topk(start_logits, k=min(K, L)).indices.tolist()
        end_top = torch.topk(end_logits, k=min(K, L)).indices.tolist()

        best_score = -float("inf")
        best_start = best_end = 0
        for s in start_top:
            if s == 0 or not ctx_mask[s]:
                continue
            for e in end_top:
                if e < s or e == 0 or not ctx_mask[e]:
                    continue
                if e - s + 1 > self.config.max_answer_len:
                    continue
                score = float(start_logits[s] + end_logits[e])
                if score > best_score:
                    best_score = score
                    best_start = s
                    best_end = e

        if best_score == -float("inf"):
            return "", 0.0

        if self.config.handle_impossible_answer and null_score >= best_score:
            return "", 0.0

        char_start = offsets[best_start][0]
        char_end = offsets[best_end][1]
        answer = context[char_start:char_end].strip()

        # Convert to a probability-like confidence via softmax over logits
        score = float(
            F.softmax(start_logits, dim=-1)[best_start]
            * F.softmax(end_logits, dim=-1)[best_end]
        )
        return answer, score

    # ---------------------------------------------------------- prediction

    def predict_record(
        self, record_id: str, abstract: str,
    ) -> Mapping[str, FieldPrediction]:
        if not abstract or not abstract.strip():
            return {f: FieldPrediction.nr() for f in HEADLINE_FIELDS}
        self._ensure_loaded()
        out: dict[str, FieldPrediction] = {}
        for field in HEADLINE_FIELDS:
            try:
                span, score = self._qa(QUESTIONS[field], abstract)
            except Exception as exc:
                LOG.warning(
                    "[%s] QA failed on %s/%s: %s",
                    self.name, record_id, field, exc,
                )
                out[field] = FieldPrediction.nr()
                continue
            if score < self.config.confidence_threshold or not span:
                out[field] = FieldPrediction.nr()
                continue
            if field in NUMERIC_FIELDS:
                out[field] = _parse_numeric_span(span, field, self._normalizer)
            else:
                out[field] = _parse_text_span(span)
        return out
