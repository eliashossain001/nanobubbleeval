"""B3: schema-constrained zero-shot LLM baseline.

Uses an open-weights instruction-tuned LLM (default: ``Qwen/Qwen2.5-7B-Instruct``)
prompted with the 18-field schema, the ``NOT_REPORTED`` convention, and a
single in-context worked example. The model returns one JSON object per
abstract; we then run a small repair pass and convert the JSON into one
:class:`FieldPrediction` per headline field.

Design principles:
    * One forward pass per record (greedy decoding for reproducibility).
    * Strict JSON parsing first, lenient repair on failure, NR fallback last.
    * No prompt-tuning on the test split; one fixed prompt template.
    * Model and tokeniser are loaded lazily (constructor is cheap; inference
      triggers download/load).

Usage:
    >>> bl = LLMBaseline(model_id="Qwen/Qwen2.5-7B-Instruct", dtype="bfloat16")
    >>> preds = bl.predict_record("r1", "Lipid nanobubbles 200 nm in diameter ...")
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Mapping, Optional

from nanobubbleval.baselines.base import Baseline, FieldPrediction
from nanobubbleval.schema import HEADLINE_FIELDS, NR, NUMERIC_FIELDS

LOG = logging.getLogger(__name__)

DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"

SYSTEM_PROMPT = (
    "You are a scientific information-extraction system for the nanobubble "
    "and nanocarrier literature. Given a paper's abstract, you extract a "
    "fixed set of physical properties as a strict JSON object. You never "
    "fabricate values: if the abstract does not state a property, return "
    "NOT_REPORTED for that field. Evidence quotes must be verbatim substrings "
    "of the input abstract."
)

USER_TEMPLATE = """Extract the following six properties from the abstract below.

Fields and their canonical units:
  1. size                  — particle or bubble diameter (canonical unit: nm)
  2. zeta_potential        — surface charge (canonical unit: mV)
  3. stability             — persistence / lifetime (canonical unit: h)
  4. payload               — drug, dye, gene, gas, or cargo loaded (text; no unit)
  5. loading_efficiency    — encapsulation / loading percentage (canonical: %)
  6. release_profile       — release behaviour (text; no unit)

For each field, return three subkeys:
  - "value":           the value (numeric or text), or "NOT_REPORTED"
  - "unit":            the unit if applicable, "" for text fields, or "NOT_REPORTED"
  - "evidence_quote":  a VERBATIM SUBSTRING of the abstract supporting the value,
                       or "NOT_REPORTED" if not stated

CRITICAL RULES:
  - "NOT_REPORTED" is a valid and important answer. Most abstracts state only
    two or three of these six fields; do not invent values for the others.
  - Evidence quotes must be exact substrings of the abstract. If you cannot
    quote it, you cannot claim it.
  - For numeric fields, return the numeric value only (e.g., "200", not "200 nm").
  - For ranges, return them as written (e.g., "150-250").

Worked example
==============
Abstract: "Lipid nanobubbles (185 +/- 22 nm, zeta potential -18 mV) loaded with
doxorubicin showed 81% encapsulation efficiency and sustained drug release over 72 h."

Output:
{{"size": {{"value": "185", "unit": "nm", "evidence_quote": "185 +/- 22 nm"}},
  "zeta_potential": {{"value": "-18", "unit": "mV", "evidence_quote": "zeta potential -18 mV"}},
  "stability": {{"value": "NOT_REPORTED", "unit": "NOT_REPORTED", "evidence_quote": "NOT_REPORTED"}},
  "payload": {{"value": "doxorubicin", "unit": "", "evidence_quote": "loaded with doxorubicin"}},
  "loading_efficiency": {{"value": "81", "unit": "%", "evidence_quote": "81% encapsulation efficiency"}},
  "release_profile": {{"value": "sustained drug release over 72 h", "unit": "", "evidence_quote": "sustained drug release over 72 h"}}}}

Abstract to extract from
========================
{abstract}

Output only the JSON object, nothing else."""


# ---------------------------------------------------------------------------
# JSON repair
# ---------------------------------------------------------------------------

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_block(text: str) -> Optional[str]:
    """Find the largest balanced JSON object in ``text``."""
    if not text:
        return None
    m = _JSON_BLOCK.search(text)
    if not m:
        return None
    return m.group(0)


def parse_llm_json(raw: str) -> Optional[dict]:
    """Strict-then-lenient JSON parsing for LLM output. Returns None on failure."""
    if not raw:
        return None
    block = _extract_json_block(raw) or raw
    try:
        return json.loads(block)
    except json.JSONDecodeError:
        pass

    # Repair pass: strip code fences, trailing commas, common quote issues.
    repaired = block
    repaired = re.sub(r"```(?:json)?\s*", "", repaired)
    repaired = re.sub(r"\s*```\s*$", "", repaired)
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    repaired = repaired.replace("“", '"').replace("”", '"')
    repaired = repaired.replace("‘", "'").replace("’", "'")
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None


def _to_prediction(raw_field: object) -> FieldPrediction:
    """Coerce one field's JSON entry into a FieldPrediction. Robust to
    missing keys, wrong types, and embedded nulls."""
    if not isinstance(raw_field, dict):
        return FieldPrediction.nr()
    v = raw_field.get("value", NR)
    u = raw_field.get("unit", "")
    e = raw_field.get("evidence_quote", NR)

    def _coerce(x: object, default: str = NR) -> str:
        if x is None:
            return default
        if isinstance(x, str):
            return x.strip() or default
        return str(x).strip()

    return FieldPrediction(
        value=_coerce(v, NR),
        unit=_coerce(u, ""),
        evidence_quote=_coerce(e, NR),
    )


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------

@dataclass
class LLMConfig:
    model_id: str = DEFAULT_MODEL
    dtype: str = "bfloat16"
    device_map: str = "auto"
    max_new_tokens: int = 512
    do_sample: bool = False     # greedy for reproducibility
    temperature: float = 0.0
    trust_remote_code: bool = False


class LLMBaseline(Baseline):
    """Open-weights instruction LLM with schema-constrained JSON output.

    Default model is ``Qwen/Qwen2.5-7B-Instruct``; pass ``model_id`` to swap.
    Loads the model lazily on first prediction.
    """

    name = "qwen25-7b-instruct"

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self.config = config or LLMConfig()
        # Override the registered name so artefacts land under the right
        # baseline directory when a non-default model is used.
        if self.config.model_id != DEFAULT_MODEL:
            self.name = self.config.model_id.split("/")[-1].lower()
        self._tokenizer = None
        self._model = None

    # ----------------------------------------------------------------- load

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        dtype = getattr(torch, self.config.dtype)
        LOG.info(
            "[%s] loading %s (dtype=%s, device_map=%s)",
            self.name, self.config.model_id, self.config.dtype, self.config.device_map,
        )
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_id,
            trust_remote_code=self.config.trust_remote_code,
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            self.config.model_id,
            dtype=dtype,
            device_map=self.config.device_map,
            trust_remote_code=self.config.trust_remote_code,
        )
        self._model.eval()
        LOG.info("[%s] model loaded", self.name)

    # ---------------------------------------------------------- prediction

    def _build_prompt(self, abstract: str) -> str:
        return USER_TEMPLATE.format(abstract=abstract.strip())

    def _generate(self, abstract: str) -> str:
        self._ensure_loaded()
        import torch

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": self._build_prompt(abstract)},
        ]
        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)
        with torch.no_grad():
            out = self._model.generate(
                **inputs,
                max_new_tokens=self.config.max_new_tokens,
                do_sample=self.config.do_sample,
                temperature=self.config.temperature,
                pad_token_id=self._tokenizer.eos_token_id,
            )
        new_tokens = out[0, inputs["input_ids"].shape[1]:]
        return self._tokenizer.decode(new_tokens, skip_special_tokens=True)

    def predict_record(
        self, record_id: str, abstract: str,
    ) -> Mapping[str, FieldPrediction]:
        if not abstract or not abstract.strip():
            return {f: FieldPrediction.nr() for f in HEADLINE_FIELDS}
        try:
            raw = self._generate(abstract)
        except Exception as exc:
            LOG.warning("[%s] generation failed for %s: %s", self.name, record_id, exc)
            return {f: FieldPrediction.nr() for f in HEADLINE_FIELDS}
        parsed = parse_llm_json(raw)
        if parsed is None:
            LOG.warning("[%s] JSON parse failed for %s", self.name, record_id)
            return {f: FieldPrediction.nr() for f in HEADLINE_FIELDS}
        return {f: _to_prediction(parsed.get(f)) for f in HEADLINE_FIELDS}
