from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple
import os

from ..pdf_text import extract_textlayer, render_pages, choose_date_prefix
from ..vision_ocr import ocr_pages_with_vision
from ..utils import alnum_ratio, redact_sensitive
from ..mapping import SenderMapper, normalize_sender
from ..naming import build_base_name, resolve_collision
from ..classifier import classify_multi_stage
from ..llm import OllamaClient
from .types import PlanItem


def _safe_stat_exists(p: Path) -> bool:
    try:
        return p.exists()
    except Exception:
        return False


def analyze_pdf(
    pdf_path: Path, cfg, mapper: SenderMapper, client: OllamaClient, logger
) -> PlanItem:
    item = PlanItem(
        input_path=pdf_path,
        original_filename=pdf_path.name,
    )

    if not _safe_stat_exists(pdf_path):
        item.status = "Error"
        item.error = "File not found (likely iCloud sync race)"
        return item

    # Extract date prefix (metadata only)
    date_prefix, _date_source = choose_date_prefix(
        pdf_path, cfg.renaming.date_source_priority
    )
    item.date_prefix = date_prefix

    # Extract text
    extraction_method = "textlayer"
    pages_processed = 0
    extracted_text = ""

    try:
        extracted_text = extract_textlayer(pdf_path)
    except Exception as e:
        logger.warning(f"Textlayer extraction failed for {pdf_path.name}: {e}")
        extracted_text = ""

    need_ocr = (len(extracted_text) < cfg.ocr.min_text_chars) or (
        alnum_ratio(extracted_text) < cfg.ocr.min_alnum_ratio
    )
    if need_ocr and cfg.ocr.use_vision:
        extraction_method = "vision_ocr"
        try:
            page_pngs = render_pages(
                pdf_path, max_pages=cfg.ocr.max_pages, dpi=cfg.ocr.dpi
            )
            ocr_res = ocr_pages_with_vision(
                page_pngs, recognition_level="accurate", languages=["de-DE", "en-US"]
            )
            extracted_text = ocr_res.text
            pages_processed = ocr_res.pages_processed
        except Exception as e:
            item.status = "Error"
            item.error = f"OCR failed: {e}"
            return item

    item.extraction_method = extraction_method
    item.pages_processed = int(pages_processed)

    extracted_text = (extracted_text or "").strip()
    text_for_llm = extracted_text[: cfg.classification.max_input_chars]

    known_senders = sorted(mapper.mapping.folders.keys())

    # LLM classify (multi-stage)
    try:
        decision = classify_multi_stage(
            client=client,
            text=text_for_llm,
            known_senders=known_senders,
            model_stage1=cfg.classification.stage1_model,
            model_stage2=cfg.classification.stage2_model,
            temperature=cfg.classification.temperature,
            threshold_accept=cfg.classification.threshold_accept,
            require_evidence=cfg.classification.require_evidence,
        )
    except Exception as e:
        item.status = "Error"
        item.error = f"LLM classify failed: {e}"
        return item

    # confidences
    item.stage_used = int(decision.stage_used)
    item.conf_stage1 = float(decision.stage1.confidence) if decision.stage1 else 0.0
    item.conf_stage2 = float(decision.stage2.confidence) if decision.stage2 else 0.0
    item.conf_final = float(decision.final.confidence)

    # final values
    item.sender = normalize_sender(decision.final.sender_canonical)
    item.document_type = decision.final.document_type or "other"
    item.filename_label = decision.final.filename_label or "Dokument"
    item.evidence = [redact_sensitive(str(x)) for x in (decision.final.evidence or [])][
        :3
    ]
    item.notes = (
        redact_sensitive(str(decision.final.notes)) if decision.final.notes else ""
    )

    # routing extras (falls vorhanden)
    item.llm_target_folder = (
        getattr(decision.final, "target_folder", "") or ""
    ).strip()
    item.llm_is_private = bool(getattr(decision.final, "is_private", False))
    item.llm_folder_reason = redact_sensitive(
        str(getattr(decision.final, "folder_reason", "") or "")
    )
    # Hard rule: private documents always go to fallback (_Unklar)
    if item.llm_is_private:
        routed_to_fallback = True
    else:
        routed_to_fallback = item.conf_final < float(
            cfg.classification.threshold_safe_to_file
        )

    # LLM folder override (optional)
    allow_override = bool(
        getattr(cfg.classification, "allow_llm_folder_override", False)
    )
    override_min_conf = float(
        getattr(cfg.classification, "llm_folder_override_min_conf", 0.85)
    )

    target_dir: Optional[Path] = None
    final_folder = ""

    if (
        (not routed_to_fallback)
        and allow_override
        and item.llm_target_folder
        and (item.conf_final >= override_min_conf)
    ):
        if (
            item.llm_target_folder.lower() in {"_unklar", "unklar", "fallback"}
            or item.llm_is_private
        ):
            routed_to_fallback = True
        else:
            final_folder = item.llm_target_folder
            target_dir = cfg.paths.documents_dir / final_folder

    # If not overridden, use mapping-based routing
    if target_dir is None:
        if routed_to_fallback:
            final_folder = cfg.paths.fallback_dir.name
            target_dir = cfg.paths.fallback_dir
        else:
            canon = mapper.canonicalize(item.sender)

            # Explain which mapping matched (F17 light)
            if canon in mapper.mapping.folders:
                item.mapping_match_type = "exact"
                item.mapping_match_value = canon
            elif item.sender in mapper.mapping.synonyms:
                item.mapping_match_type = "synonym"
                item.mapping_match_value = item.sender
            else:
                item.mapping_match_type = "none"
                item.mapping_match_value = ""

            folder = mapper.folder_for(canon)

            if folder is None:
                folder = canon
                if cfg.mapping.route_unknown_sender_to_fallback:
                    final_folder = cfg.paths.fallback_dir.name
                    target_dir = cfg.paths.fallback_dir
                    routed_to_fallback = True
                else:
                    final_folder = folder
                    target_dir = cfg.paths.documents_dir / final_folder
            else:
                final_folder = folder
                target_dir = cfg.paths.documents_dir / final_folder

    item.target_folder = final_folder

    # Filename build
    hint = (
        "Unklar" if routed_to_fallback else (final_folder or item.sender or "").strip()
    )
    name_stem_source = item.filename_label.strip() or "Dokument"
    if hint:
        name_stem_source = f"{name_stem_source} {hint}".strip()

    base_name = build_base_name(
        date_prefix=date_prefix,
        original_stem=name_stem_source,
        separator=cfg.renaming.separator,
        keep_umlauts=cfg.renaming.keep_umlauts,
        max_len=cfg.renaming.filename_max_len,
    )

    ext = pdf_path.suffix if pdf_path.suffix else ".pdf"
    planned_target = resolve_collision(
        target_dir=target_dir,
        base_name=base_name,
        ext=ext,
        suffix_format=cfg.renaming.collision_suffix_format,
        max_suffix=cfg.renaming.max_suffix,
    )

    item.planned_target_path = planned_target
    item.status = "Pending"
    return item


def list_input_pdfs(input_dir: Path) -> List[Path]:
    if not input_dir.exists():
        return []
    return sorted(
        [p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"]
    )
