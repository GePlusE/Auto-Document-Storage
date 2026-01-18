from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Dict, Any, Optional
import os
import json

from rich.console import Console
from rich.table import Table

from .config import load_config
from .logging_setup import setup_logging
from .scanner import list_pdfs
from .pdf_text import (
    extract_textlayer,
    render_pages,
    choose_date_prefix,
    get_pdf_metadata_date,
    get_file_birthtime_date,
)
from .vision_ocr import ocr_pages_with_vision
from .utils import alnum_ratio, redact_sensitive, file_fingerprint_sha256
from .mapping import load_sender_mapping, SenderMapper, normalize_sender
from .naming import build_base_name, resolve_collision
from .llm import OllamaClient
from .classifier import classify_multi_stage
from .mover import move_file, ensure_dir
from .db import Database


def _run_id() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def process_one(
    pdf_path: Path,
    cfg,
    mapper: SenderMapper,
    client: OllamaClient,
    db: Database,
    run_id: str,
    dry_run: bool,
    logger,
) -> Dict[str, Any]:
    started_at = dt.datetime.now().isoformat(timespec="seconds")
    error: Optional[str] = None

    # File meta
    file_size = pdf_path.stat().st_size
    file_birth = None
    try:
        st = os.stat(pdf_path)
        bt = getattr(st, "st_birthtime", None)
        if bt is not None:
            file_birth = dt.datetime.fromtimestamp(bt).isoformat(timespec="seconds")
    except Exception:
        pass

    pdf_meta_date = get_pdf_metadata_date(pdf_path)
    pdf_meta_created_at = pdf_meta_date.isoformat() if pdf_meta_date else None

    original_filename = pdf_path.name
    original_stem = pdf_path.stem

    # Fingerprint for caching (stable across rename/path)
    try:
        fingerprint = file_fingerprint_sha256(pdf_path)
    except Exception:
        fingerprint = ""

    # Date prefix (metadata only)
    date_prefix, date_source = choose_date_prefix(
        pdf_path, cfg.renaming.date_source_priority
    )

    # Extract text (textlayer -> OCR if needed)
    extraction_method = "textlayer"
    pages_processed = 0
    extracted_text = ""
    try:
        extracted_text = extract_textlayer(pdf_path)
        pages_processed = 0  # not tracked in textlayer for now
    except Exception as e:
        # Treat as empty; try OCR
        logger.warning(f"Textlayer extraction failed for {pdf_path.name}: {e}")
        extracted_text = ""

    # Decide if OCR needed
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
            error = f"OCR failed: {e}"
            extracted_text = extracted_text or ""

    extracted_text = (extracted_text or "").strip()
    extracted_char_count = len(extracted_text)

    # Truncate input to LLM
    text_for_llm = extracted_text[: cfg.classification.max_input_chars]
    known_senders = sorted(mapper.mapping.folders.keys())
    existing_folders = sorted(
        [d.name for d in cfg.paths.documents_dir.iterdir() if d.is_dir()]
    )

    # Classify
    routed_to_fallback = 0
    final_sender = ""
    final_conf = 0.0
    final_doc_type = "other"
    filename_label = "Dokument"
    final_evidence = []
    final_notes = ""
    llm_target_folder = ""
    llm_is_private = False
    llm_folder_reason = ""
    final_folder = ""
    final_target_path = ""
    target_dir = None
    stage_used = 0
    raw1 = raw2 = raw_final = None
    model1 = cfg.classification.stage1_model
    model2 = cfg.classification.stage2_model

    try:
        decision = classify_multi_stage(
            client=client,
            text=text_for_llm,
            known_senders=known_senders,
            existing_folders=existing_folders,
            model_stage1=model1,
            model_stage2=model2,
            temperature=cfg.classification.temperature,
            threshold_accept=cfg.classification.threshold_accept,
            require_evidence=cfg.classification.require_evidence,
        )
        stage_used = decision.stage_used
        raw1 = decision.stage1.raw_json if decision.stage1 else None
        raw2 = decision.stage2.raw_json if decision.stage2 else None
        raw_final = decision.final.raw_json if decision.final else None

        final_sender = normalize_sender(decision.final.sender_canonical)
        final_conf = float(decision.final.confidence)
        final_doc_type = decision.final.document_type or "other"
        filename_label = (
            getattr(decision.final, "filename_label", "Dokument") or "Dokument"
        )
        final_evidence = getattr(decision.final, "evidence", []) or []
        final_notes = getattr(decision.final, "notes", "") or ""
        llm_target_folder = getattr(decision.final, "target_folder", "") or ""
        llm_is_private = bool(getattr(decision.final, "is_private", False))
        llm_folder_reason = getattr(decision.final, "folder_reason", "") or ""

    except Exception as e:
        error = error or f"LLM classify failed: {e}"
        # Ensure we still have a meaningful label in case LLM fails
        filename_label = "Dokument"

    # Decide routing to fallback
    if error:
        routed_to_fallback = 1
    elif final_conf < cfg.classification.threshold_safe_to_file:
        routed_to_fallback = 1

    # Optional: LLM can suggest a target folder (topic-based routing).
    # Apply only if confidence is high and suggestion is non-empty.
    try:
        allow_override = bool(
            getattr(cfg.classification, "allow_llm_folder_override", False)
        )
        override_min_conf = float(
            getattr(cfg.classification, "llm_folder_override_min_conf", 0.85)
        )
    except Exception:
        allow_override = False
        override_min_conf = 0.85

    llm_target_folder = (llm_target_folder or "").strip()

    if (
        (not error)
        and allow_override
        and llm_target_folder
        and (final_conf >= override_min_conf)
    ):
        # Normalize some common "fallback" suggestions
        if (
            llm_target_folder.lower() in {"_unklar", "unklar", "fallback"}
            or llm_is_private
        ):
            routed_to_fallback = 1
            final_folder = cfg.paths.fallback_dir.name
            target_dir = cfg.paths.fallback_dir
        else:
            # Use the LLM folder directly under documents_dir
            final_folder = llm_target_folder
            target_dir = cfg.paths.documents_dir / final_folder

    # Resolve folder (unless already decided by LLM override)
    if target_dir is None:
        if routed_to_fallback:
            final_folder = cfg.paths.fallback_dir.name  # for logging
            target_dir = cfg.paths.fallback_dir
        else:
            canon = mapper.canonicalize(final_sender)
            folder = mapper.folder_for(canon)
            if folder is None:
                # Unknown sender folder name -> use canonical (sanitized later)
                folder = canon
                if cfg.mapping.route_unknown_sender_to_fallback:
                    routed_to_fallback = 1
                    target_dir = cfg.paths.fallback_dir
                    final_folder = cfg.paths.fallback_dir.name
                else:
                    target_dir = cfg.paths.documents_dir / folder
                    final_folder = folder
            else:
                target_dir = cfg.paths.documents_dir / folder
                final_folder = folder

    # Build new filename + handle collisions
    # Human-friendly stem: label + hint (folder/sender), but keep it short.
    hint = ""
    if routed_to_fallback:
        hint = "Unklar"
    else:
        hint = (final_folder or "").strip() or (final_sender or "").strip()

    filename_label = (filename_label or "Dokument").strip() or "Dokument"
    name_stem_source = filename_label.strip()
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
    final_target_path = str(planned_target)
    final_final_filename = planned_target.name

    # Execute move
    if not dry_run:
        ensure_dir(target_dir)
        move_file(pdf_path, planned_target)

    naming_template_used = ""
    try:
        naming_template_used = str(getattr(cfg.renaming, "naming_template", "") or "")
    except Exception:
        naming_template_used = ""

    # Insert DB row
    row = {
        "run_id": run_id,
        "input_path": str(pdf_path),
        "original_filename": original_filename,
        "file_fingerprint": fingerprint,
        "naming_template": naming_template_used,
        "file_size_bytes": int(file_size),
        "file_created_at": file_birth,
        "pdf_meta_created_at": pdf_meta_created_at,
        "chosen_date_prefix": date_prefix,
        "date_source": date_source,
        "extraction_method": extraction_method,
        "pages_processed": int(pages_processed),
        "extracted_char_count": int(extracted_char_count),
        "final_sender_canonical": final_sender,
        "final_confidence": float(final_conf),
        "final_document_type": final_doc_type,
        "final_filename_label": filename_label,
        "final_evidence": json.dumps(
            [redact_sensitive(str(x)) for x in (final_evidence or [])][:3],
            ensure_ascii=False,
        ),
        "final_notes": redact_sensitive(str(final_notes)) if final_notes else "",
        "final_final_filename": final_final_filename,
        "final_target_folder": final_folder,
        "final_target_path": final_target_path,
        "routed_to_fallback": int(routed_to_fallback),
        "stage_used": int(stage_used),
        "llm_model_stage1": model1,
        "llm_model_stage2": model2,
        "llm_target_folder": (llm_target_folder or "").strip() or None,
        "llm_is_private": int(bool(llm_is_private)),
        "llm_folder_reason": (
            redact_sensitive(str(llm_folder_reason)).strip()
            if llm_folder_reason
            else None
        ),
        "llm_raw_json_stage1": redact_sensitive(raw1) if raw1 else None,
        "llm_raw_json_stage2": redact_sensitive(raw2) if raw2 else None,
        "llm_raw_json_final": redact_sensitive(raw_final) if raw_final else None,
        "error": error,
        "processed_at": started_at,
    }
    db.insert_document(row)
    return row


def main():
    parser = argparse.ArgumentParser(
        prog="pdf-filer",
        description="Local PDF auto-filing on macOS (Vision OCR + Ollama).",
    )

    sub = parser.add_subparsers(dest="cmd", required=False)

    run_p = sub.add_parser("run", help="Run one processing cycle")
    gui_p = sub.add_parser("gui", help="Launch GUI for reviewing PDFs")
    gui_p.add_argument("--config", required=True, help="Path to config.yaml")
    gui_p.add_argument("--verbose", action="store_true", help="Verbose logging")

    run_p.add_argument("--config", required=True, help="Path to config.yaml")

    run_p.add_argument(
        "--dry-run", action="store_true", help="Do not move/rename files"
    )

    run_p.add_argument("--verbose", action="store_true", help="Verbose logging")

    run_p.add_argument(
        "--limit", type=int, default=0, help="Max number of PDFs to process (0=all)"
    )

    args = parser.parse_args()
    if args.cmd is None:
        args.cmd = "run"

    cfg = load_config(Path(args.config))
    logger = setup_logging(
        cfg.paths.logs_dir, verbose=bool(getattr(args, "verbose", False))
    )
    console = Console()

    # GUI command
    if args.cmd == "gui":
        from .mapping import load_sender_mapping, SenderMapper
        from .llm import OllamaClient
        from .gui.app import run_gui

        mapping = load_sender_mapping(cfg.paths.mapping_json)
        mapper = SenderMapper(mapping)
        client = OllamaClient(
            cfg.classification.ollama_host,
            timeout_seconds=cfg.classification.timeout_seconds,
        )
        run_gui(cfg, mapper, client, logger)
        return

    mapping = load_sender_mapping(cfg.paths.mapping_json)
    mapper = SenderMapper(mapping)
    client = OllamaClient(
        cfg.classification.ollama_host,
        timeout_seconds=cfg.classification.timeout_seconds,
    )
    db = Database(cfg.paths.db_path)

    run_id = _run_id()
    db.start_run(run_id)

    counts = {"total": 0, "success": 0, "fallback": 0, "failed": 0}

    try:
        pdfs = list_pdfs(cfg.paths.input_dir, recursive=False)
        if args.limit and args.limit > 0:
            pdfs = pdfs[: args.limit]

        table = Table(title=f"pdf-filer run {run_id}")
        table.add_column("File")
        table.add_column("Sender")
        table.add_column("Conf", justify="right")
        table.add_column("Dest")
        table.add_column("Status")
        table.add_column("Error")

        for pdf in pdfs:
            counts["total"] += 1
            try:
                row = process_one(
                    pdf,
                    cfg,
                    mapper,
                    client,
                    db,
                    run_id,
                    dry_run=bool(args.dry_run),
                    logger=logger,
                )
                status = "FALLBACK" if row.get("routed_to_fallback") else "OK"
                if row.get("error"):
                    status = "FAILED"
                    counts["failed"] += 1
                else:
                    if row.get("routed_to_fallback"):
                        counts["fallback"] += 1
                    else:
                        counts["success"] += 1

                table.add_row(
                    pdf.name,
                    row.get("final_sender_canonical") or "",
                    f"{row.get('final_confidence', 0.0):.2f}",
                    Path(row.get("final_target_path") or "").parent.name,
                    status,
                    (row.get("error") or "")[:80],
                )

            except Exception as e:
                logger.exception(f"Processing failed for {pdf}: {e}")
                counts["failed"] += 1
                table.add_row(pdf.name, "", "", "", "FAILED")

        console.print(table)
        logger.info(f"Run summary: {counts}")

    finally:
        db.end_run(run_id, counts)
        db.close()


if __name__ == "__main__":
    main()
