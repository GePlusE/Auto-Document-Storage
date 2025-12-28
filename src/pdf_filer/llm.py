from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Tuple
import json
import re
import requests


@dataclass(frozen=True)
class LLMResult:
    sender_canonical: str
    confidence: float
    evidence: List[str]
    document_type: str
    filename_label: str
    notes: str
    is_private: bool
    target_folder: str
    folder_reason: str
    raw_json: str
    model: str


_JSON_OBJ_RE = re.compile(r"\{.*?\}", re.DOTALL)


def _safe_parse_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    # Try direct parse first
    try:
        return json.loads(text)
    except Exception:
        # Try to extract the first JSON object
        m = _JSON_OBJ_RE.search(text)
        if not m:
            raise
        return json.loads(m.group(0))


def build_prompt(extracted_text: str, known_senders: List[str]) -> str:
    # Keep it short and directive; known senders help the model choose canonical names.
    # IMPORTANT: We do NOT include full mapping JSON; we pass only canonical names list.
    ks = "\n".join(f"- {s}" for s in known_senders[:300])  # safety cap

    # Use custom delimiters instead of triple quotes inside the f-string.
    return f"""You are a document classifier.
        Task: Identify the most likely sender/company (German documents) from the text below.

        Return ONLY strict JSON matching this schema:
        {{
        "sender_canonical": string,
        "confidence": number,         // 0.0..1.0
        "evidence": [string],         // up to 3 short snippets (<=120 chars each)
        "document_type": string,      // invoice|letter|contract|insurance|other
        "filename_label": string,     // short German label for filename (see rules)
        "notes": string,
        "is_private": boolean,
        "target_folder": string,
        "folder_reason": string
        }}

        Rules:
        - If uncertain, set confidence < 0.7.
        - Prefer a sender name from Known Senders if it matches.
        - filename_label must be a short German noun phrase, 1–3 words (e.g. "Rechnung", "Mahnung", "Informationsschreiben", "Vertrag", "Gehaltsabrechnug").
        - Do NOT include dates, invoice numbers, customer numbers, names, addresses, IBAN, or other sensitive data in filename_label.
        - No digits in filename_label. No special characters other than spaces and German letters.
        - If you cannot decide, use "Dokument".
        - Output JSON only. No markdown, no commentary.
        - Set is_private=true for greeting cards / personal congratulations / private letters not from companies.


        Known Senders:
        {ks}

        Document Text (may contain OCR noise):
        <<<BEGIN_TEXT
        {extracted_text}
        END_TEXT>>>
        """


class OllamaClient:
    def __init__(self, host: str, timeout_seconds: int = 90):
        self.host = host.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate_json(self, model: str, prompt: str, temperature: float = 0.0) -> str:
        # Ollama /api/generate supports 'format': 'json' in many versions.
        # We still parse defensively in case the model outputs extra text.
        url = f"{self.host}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
            "format": "json",
        }
        r = requests.post(url, json=payload, timeout=self.timeout_seconds)
        r.raise_for_status()
        data = r.json()
        # For non-stream generate: response text under 'response'
        return str(data.get("response", "")).strip()


def _normalize_filename_label(label: str) -> str:
    label = (label or "").strip()

    # Collapse whitespace
    label = re.sub(r"\s+", " ", label)

    # Remove surrounding quotes/punctuation
    label = label.strip(" .-_\"'“”„")

    # Hard rules: no digits, keep it short
    if not label:
        return "Dokument"
    if re.search(r"\d", label):
        return "Dokument"

    # Keep only letters/spaces (incl. German umlauts) and basic punctuation removal
    # (We keep spaces; everything else becomes space)
    label = re.sub(r"[^A-Za-zÄÖÜäöüß ]+", " ", label)
    label = re.sub(r"\s+", " ", label).strip()

    # 1–3 words
    words = label.split()
    if len(words) == 0:
        return "Dokument"
    if len(words) > 3:
        label = " ".join(words[:3])

    # Limit length
    if len(label) > 32:
        label = label[:32].rstrip()

    return label or "Dokument"


def to_llm_result(raw_json_text: str, model: str) -> LLMResult:
    obj = _safe_parse_json(raw_json_text)
    sender = str(obj.get("sender_canonical", "")).strip()
    try:
        conf = float(obj.get("confidence", 0.0))
    except Exception:
        conf = 0.0
    evidence = obj.get("evidence", []) or []
    if not isinstance(evidence, list):
        evidence = [str(evidence)]
    evidence = [str(x)[:120] for x in evidence[:3]]
    doc_type = str(obj.get("document_type", "other")).strip() or "other"
    filename_label_raw = str(obj.get("filename_label", "Dokument"))
    filename_label = _normalize_filename_label(filename_label_raw)
    notes = str(obj.get("notes", "")).strip()

    is_private = bool(obj.get("is_private", False))
    target_folder = str(obj.get("target_folder", "")).strip()
    folder_reason = str(obj.get("folder_reason", "")).strip()

    return LLMResult(
        sender_canonical=sender,
        confidence=max(0.0, min(1.0, conf)),
        evidence=evidence,
        document_type=doc_type,
        filename_label=filename_label,
        notes=notes,
        is_private=is_private,
        target_folder=target_folder,
        folder_reason=folder_reason,
        raw_json=raw_json_text,
        model=model,
    )
