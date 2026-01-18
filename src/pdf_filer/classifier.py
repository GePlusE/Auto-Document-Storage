from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .llm import OllamaClient, build_prompt, to_llm_result, LLMResult


@dataclass(frozen=True)
class ClassificationDecision:
    final: LLMResult
    stage_used: int
    stage1: Optional[LLMResult]
    stage2: Optional[LLMResult]


def classify_multi_stage(
    client: OllamaClient,
    text: str,
    known_senders: List[str],
    existing_folders: List[str],
    model_stage1: str,
    model_stage2: str,
    temperature: float,
    threshold_accept: float,
    require_evidence: bool,
) -> ClassificationDecision:
    prompt = build_prompt(text, known_senders, existing_folders)

    raw1 = client.generate_json(model_stage1, prompt, temperature=temperature)
    r1 = to_llm_result(raw1, model_stage1)

    def good_enough(r: LLMResult) -> bool:
        if r.confidence < threshold_accept:
            return False
        if require_evidence and (not r.evidence or len(r.evidence) == 0):
            return False
        return True

    if good_enough(r1):
        return ClassificationDecision(final=r1, stage_used=1, stage1=r1, stage2=None)

    raw2 = client.generate_json(model_stage2, prompt, temperature=temperature)
    r2 = to_llm_result(raw2, model_stage2)

    # Pick higher confidence; if tie, prefer stage2.
    final = r2 if (r2.confidence >= r1.confidence) else r1
    used = 2 if final is r2 else 1
    return ClassificationDecision(final=final, stage_used=used, stage1=r1, stage2=r2)
