from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

# macOS-only via PyObjC
import Vision
import Quartz
import Cocoa


@dataclass(frozen=True)
class OCRResult:
    text: str
    pages_processed: int


def _cgimage_from_png_bytes(png_bytes: bytes):
    ns_data = Cocoa.NSData.dataWithBytes_length_(png_bytes, len(png_bytes))
    ns_image = Cocoa.NSImage.alloc().initWithData_(ns_data)
    if ns_image is None:
        raise RuntimeError("Failed to decode PNG bytes into NSImage")
    cgimage_ref = ns_image.CGImageForProposedRect_context_hints_(None, None, None)[0]
    if cgimage_ref is None:
        # Fallback: create CGImage via NSBitmapImageRep
        reps = ns_image.representations()
        if reps and len(reps) > 0:
            rep = reps[0]
            cgimage_ref = rep.CGImage()
    if cgimage_ref is None:
        raise RuntimeError("Failed to obtain CGImage from NSImage")
    return cgimage_ref


def ocr_pages_with_vision(page_pngs: List[bytes], recognition_level: str = "accurate", languages=None) -> OCRResult:
    """Runs VNRecognizeTextRequest on a list of page PNG bytes.
    recognition_level: 'accurate' or 'fast'
    """
    if languages is None:
        languages = ["de-DE", "en-US"]

    all_text = []
    pages = 0

    for png in page_pngs:
        cgimg = _cgimage_from_png_bytes(png)

        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate
                                     if recognition_level == "accurate"
                                     else Vision.VNRequestTextRecognitionLevelFast)
        request.setUsesLanguageCorrection_(True)
        request.setRecognitionLanguages_(languages)

        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cgimg, None)
        ok, err = handler.performRequests_error_([request], None)
        if not ok:
            raise RuntimeError(f"Vision OCR failed: {err}")

        observations = request.results() or []
        page_lines = []
        for obs in observations:
            top = obs.topCandidates_(1)
            if top and len(top) > 0:
                cand = top[0]
                page_lines.append(str(cand.string()))
        all_text.append("\n".join(page_lines))
        pages += 1

    return OCRResult(text="\n\n".join(all_text).strip(), pages_processed=pages)
