"""Creative (image) intake, OCR and measurable visual checks.

Everything here is deterministic and reproducible for a given image:
  * OCR: RapidOCR (PaddleOCR models on ONNX Runtime), run locally, no external API.
  * Contrast: WCAG 2.x contrast ratio between the two dominant colours inside each OCR
    text box (a 2-means split; the smaller cluster is treated as the glyph colour).
  * Palette: share of the image covered by colours far (CIE76 ΔE) from the brand palette.
  * Logo: multi-scale normalised cross-correlation against the workspace's reference logo.
    A high score means "looks similar", not "is authentic".
"""
import hashlib
import io
import json
import threading
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 4 * 1024 * 1024  # Vercel request bodies are capped at 4.5 MB
MIN_SIDE, MAX_SIDE = 64, 6000
MAX_PIXELS = 30_000_000
OCR_MAX_SIDE = 1600
LOW_OCR_CONFIDENCE = 0.80
PALETTE_DELTA_E = 25.0
PALETTE_MIN_SHARE = 0.08
LOGO_STRONG, LOGO_WEAK = 0.80, 0.60

Image.MAX_IMAGE_PIXELS = MAX_PIXELS

_ocr_engine = None
_ocr_lock = threading.Lock()


class ImageValidationError(ValueError):
    pass


def validate_image(data: bytes) -> Tuple[Image.Image, str]:
    """Validates by content (magic bytes + full decode), never by filename or client MIME type."""
    if not data:
        raise ImageValidationError("The file is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageValidationError(f"The image is {len(data) / 1024 / 1024:.1f} MB; the limit is {MAX_IMAGE_BYTES // 1024 // 1024} MB.")
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "image/png"
    elif data[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
    else:
        raise ImageValidationError("Unsupported file type. Upload a PNG or JPEG image.")
    try:
        probe = Image.open(io.BytesIO(data))
        probe.verify()  # structural check
        img = Image.open(io.BytesIO(data))
        img.load()  # full decode catches truncated files
    except Image.DecompressionBombError:
        raise ImageValidationError("The image has too many pixels to process safely.")
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise ImageValidationError("The image is corrupt or could not be decoded.")
    if img.format not in ("PNG", "JPEG"):
        raise ImageValidationError("Unsupported image format. Upload a PNG or JPEG image.")
    w, h = img.size
    if min(w, h) < MIN_SIDE or max(w, h) > MAX_SIDE:
        raise ImageValidationError(f"Image dimensions {w}×{h} are outside the supported range ({MIN_SIDE}–{MAX_SIDE} px per side).")
    img = ImageOps.exif_transpose(img).convert("RGB")
    return img, mime


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

def _engine():
    global _ocr_engine
    with _ocr_lock:
        if _ocr_engine is None:
            from rapidocr_onnxruntime import RapidOCR
            _ocr_engine = RapidOCR()
        return _ocr_engine


def run_ocr(img: Image.Image) -> Dict:
    """Returns {'engine', 'lines': [{text, confidence, box:[x0,y0,x1,y1], start, end}], 'text', 'status'}."""
    scale = min(1.0, OCR_MAX_SIDE / max(img.size))
    work = img if scale == 1.0 else img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    try:
        result, _ = _engine()(np.asarray(work)[:, :, ::-1])  # RapidOCR expects BGR
    except Exception as exc:  # engine missing or failed: report it, never fabricate text
        return {"engine": "rapidocr-onnxruntime", "status": "unavailable", "error": str(exc)[:200], "lines": [], "text": ""}
    lines = []
    for quad, text, conf in sorted(result or [], key=lambda r: (min(p[1] for p in r[0]), min(p[0] for p in r[0]))):
        text = str(text).strip()
        if not text:
            continue
        xs = [p[0] / scale for p in quad]
        ys = [p[1] / scale for p in quad]
        lines.append({
            "text": text,
            "confidence": round(float(conf), 3),
            "box": [int(max(0, min(xs))), int(max(0, min(ys))), int(min(img.width, max(xs))), int(min(img.height, max(ys)))],
        })
    offset, parts = 0, []
    for ln in lines:
        ln["start"], ln["end"] = offset, offset + len(ln["text"])
        parts.append(ln["text"])
        offset = ln["end"] + 1
    return {"engine": "rapidocr-onnxruntime", "status": "ok", "lines": lines, "text": "\n".join(parts)}


def regions_for_span(ocr: Dict, start: int, end: int) -> List[Dict]:
    """Maps a character span of the OCR transcript back to the text boxes it came from."""
    out = []
    for i, ln in enumerate(ocr.get("lines", [])):
        if ln["start"] < max(end, start + 1) and start < ln["end"] + 1:
            out.append({"box": ln["box"], "line": i, "ocr_confidence": ln["confidence"]})
    return out


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"'{h}' is not a hex colour")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*[int(round(c)) for c in rgb])


def _lin(c: np.ndarray) -> np.ndarray:
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def relative_luminance(rgb) -> float:
    r, g, b = _lin(np.asarray(rgb, dtype=float))
    return float(0.2126 * r + 0.7152 * g + 0.0722 * b)


def contrast_ratio(a, b) -> float:
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    rgb = _lin(np.asarray(rgb, dtype=float).reshape(-1, 3))
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = rgb @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], axis=1)


def _two_means(pixels: np.ndarray, iters: int = 12):
    lum = pixels @ np.array([0.299, 0.587, 0.114])
    c = np.array([pixels[lum.argmin()], pixels[lum.argmax()]], dtype=float)
    labels = np.zeros(len(pixels), dtype=int)
    for _ in range(iters):
        d = ((pixels[:, None, :] - c[None, :, :]) ** 2).sum(axis=2)
        labels = d.argmin(axis=1)
        for k in (0, 1):
            if (labels == k).any():
                c[k] = pixels[labels == k].mean(axis=0)
    return c, labels


# ---------------------------------------------------------------------------
# Visual checks
# ---------------------------------------------------------------------------

def check_contrast(img: Image.Image, ocr: Dict) -> List[Dict]:
    arr = np.asarray(img, dtype=float)
    results = []
    for i, ln in enumerate(ocr.get("lines", [])):
        x0, y0, x1, y1 = ln["box"]
        if x1 - x0 < 4 or y1 - y0 < 4:
            continue
        crop = arr[y0:y1, x0:x1].reshape(-1, 3)
        if len(crop) > 6000:
            crop = crop[np.linspace(0, len(crop) - 1, 6000).astype(int)]
        centers, labels = _two_means(crop)
        share = np.bincount(labels, minlength=2) / len(labels)
        text_k = int(share.argmin())
        text_rgb, bg_rgb = centers[text_k], centers[1 - text_k]
        ratio = contrast_ratio(text_rgb, bg_rgb)
        bg_std = float(crop[labels == 1 - text_k].std(axis=0).mean()) if (labels == 1 - text_k).any() else 0.0
        large = (y1 - y0) >= 32  # ~24px glyph height ≈ WCAG "large text" (18pt)
        threshold = 3.0 if large else 4.5
        uncertain = bg_std > 22 or share.min() < 0.04
        results.append({
            "line": i, "text": ln["text"], "box": ln["box"], "ratio": round(float(ratio), 2), "threshold": threshold,
            "large_text": bool(large), "text_color": rgb_to_hex(text_rgb), "background_color": rgb_to_hex(bg_rgb),
            "background_variation": round(bg_std, 1), "uncertain": bool(uncertain), "passes": bool(ratio >= threshold),
        })
    return results


def check_palette(img: Image.Image, palette_hex: List[str]) -> Dict:
    small = img.copy()
    small.thumbnail((256, 256))
    q = small.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[: 8 * 3]
    counts = sorted(q.getcolors() or [], reverse=True)
    total = sum(c for c, _ in counts) or 1
    brand_rgb = []
    for h in palette_hex:
        try:
            brand_rgb.append(hex_to_rgb(h))
        except ValueError:
            continue
    brand_lab = rgb_to_lab(np.array(brand_rgb)) if brand_rgb else np.zeros((0, 3))
    colours = []
    for count, idx in counts:
        rgb = pal[idx * 3: idx * 3 + 3]
        lab = rgb_to_lab(np.array(rgb))[0]
        chroma = float(np.hypot(lab[1], lab[2]))
        neutral = chroma < 12 and (lab[0] > 90 or lab[0] < 12)  # near-white / near-black are always allowed
        if len(brand_lab):
            d = np.sqrt(((brand_lab - lab) ** 2).sum(axis=1))
            nearest = int(d.argmin())
            delta = float(d[nearest])
            nearest_hex = palette_hex[nearest]
        else:
            delta, nearest_hex = None, None
        colours.append({
            "hex": rgb_to_hex(rgb), "share": round(count / total, 3), "neutral": bool(neutral),
            "nearest_brand_color": nearest_hex, "delta_e": None if delta is None else round(delta, 1),
            "on_palette": bool(neutral or (delta is not None and delta <= PALETTE_DELTA_E)),
        })
    off = [c for c in colours if not c["on_palette"] and c["share"] >= PALETTE_MIN_SHARE]
    return {
        "brand_palette": palette_hex, "colours": colours, "off_palette": off,
        "off_palette_share": round(sum(c["share"] for c in colours if not c["on_palette"]), 3),
        "threshold_delta_e": PALETTE_DELTA_E, "min_share": PALETTE_MIN_SHARE,
    }


def check_logo(img: Image.Image, logo: Optional[Image.Image]) -> Dict:
    if logo is None:
        return {"status": "not_configured", "detail": "No reference logo is configured for this workspace, so logo similarity was not checked."}
    try:
        import cv2
    except ImportError:
        return {"status": "unavailable", "detail": "Template matching (OpenCV) is not installed on this server."}
    scene = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2GRAY)
    tmpl_full = cv2.cvtColor(np.asarray(logo.convert("RGB")), cv2.COLOR_RGB2GRAY)
    scale_scene = min(1.0, 1200 / max(scene.shape))
    if scale_scene < 1.0:
        scene = cv2.resize(scene, None, fx=scale_scene, fy=scale_scene, interpolation=cv2.INTER_AREA)
    best = (-1.0, None, None)
    for frac in np.linspace(0.06, 0.45, 14):
        tw = int(scene.shape[1] * frac)
        th = int(tw * tmpl_full.shape[0] / tmpl_full.shape[1])
        if tw < 16 or th < 8 or th >= scene.shape[0] or tw >= scene.shape[1]:
            continue
        tmpl = cv2.resize(tmpl_full, (tw, th), interpolation=cv2.INTER_AREA)
        if tmpl.std() < 1:
            continue
        res = cv2.matchTemplate(scene, tmpl, cv2.TM_CCOEFF_NORMED)
        _, mx, _, loc = cv2.minMaxLoc(res)
        if mx > best[0]:
            best = (float(mx), loc, (tw, th))
    score, loc, size = best
    if loc is None:
        return {"status": "not_found", "score": 0.0, "detail": "The image is too small to search for the reference logo."}
    box = [int(loc[0] / scale_scene), int(loc[1] / scale_scene), int((loc[0] + size[0]) / scale_scene), int((loc[1] + size[1]) / scale_scene)]
    status = "match" if score >= LOGO_STRONG else "weak_match" if score >= LOGO_WEAK else "not_found"
    return {"status": status, "score": round(score, 3), "box": box if status != "not_found" else None,
            "thresholds": {"match": LOGO_STRONG, "weak_match": LOGO_WEAK},
            "detail": "Normalised cross-correlation against the reference logo. Similarity is not proof of authenticity, "
                      "and recoloured or distorted logos may score low."}


def analyse_visuals(img: Image.Image, ocr: Dict, palette_hex: List[str], logo: Optional[Image.Image]) -> Dict:
    return {"contrast": check_contrast(img, ocr), "palette": check_palette(img, palette_hex), "logo": check_logo(img, logo)}


def visual_findings(visual: Dict, ocr: Dict) -> List[Dict]:
    """Converts measured visual results into findings with the region that produced them."""
    out = []
    for c in visual.get("contrast", []):
        if c["passes"]:
            continue
        sev = "high" if c["ratio"] < 3.0 else "medium"
        conf = 0.55 if c["uncertain"] else 0.85
        out.append({
            "rule_id": None, "category": "visual_contrast", "severity": sev, "matched_text": c["text"],
            "start_offset": 0, "end_offset": 0,
            "explanation": (f"Estimated text contrast is {c['ratio']}:1 ({c['text_color']} on {c['background_color']}); "
                            f"WCAG AA needs {c['threshold']}:1 for {'large' if c['large_text'] else 'normal'} text."
                            + (" The background behind this text varies, so the estimate is less reliable." if c["uncertain"] else "")),
            "source_reference": "WCAG 2.2 SC 1.4.3 Contrast (Minimum)",
            "suggested_correction": None, "confidence": conf, "requires_human_review": c["uncertain"],
            "finding_source": "visual", "region_json": json.dumps([{"box": c["box"], "line": c["line"]}]),
        })
    pal = visual.get("palette", {})
    for col in pal.get("off_palette", []):
        out.append({
            "rule_id": None, "category": "visual_palette", "severity": "low", "matched_text": col["hex"],
            "start_offset": 0, "end_offset": 0,
            "explanation": (f"{col['hex']} covers about {int(col['share'] * 100)}% of the creative and is ΔE {col['delta_e']} from the "
                            f"nearest brand colour {col['nearest_brand_color']} (allowed: ΔE ≤ {pal['threshold_delta_e']}). "
                            "Photography can legitimately contain off-palette colours; review in context."),
            "source_reference": "Workspace brand palette",
            "suggested_correction": None, "confidence": 0.7, "requires_human_review": True,
            "finding_source": "visual", "region_json": None,
        })
    logo = visual.get("logo", {})
    if logo.get("status") in ("not_found", "weak_match"):
        out.append({
            "rule_id": None, "category": "visual_logo", "severity": "low" if logo["status"] == "weak_match" else "medium",
            "matched_text": "Reference logo", "start_offset": 0, "end_offset": 0,
            "explanation": (f"Best similarity to the reference logo is {logo.get('score', 0)} "
                            f"({'weak match' if logo['status'] == 'weak_match' else 'not detected'}; a match needs ≥ {LOGO_STRONG}). "
                            + logo.get("detail", "")),
            "source_reference": "Workspace reference logo", "suggested_correction": None, "confidence": 0.6,
            "requires_human_review": True, "finding_source": "visual",
            "region_json": json.dumps([{"box": logo["box"]}]) if logo.get("box") else None,
        })
    for i, ln in enumerate(ocr.get("lines", [])):
        if ln["confidence"] < LOW_OCR_CONFIDENCE:
            out.append({
                "rule_id": None, "category": "ocr_uncertain", "severity": "low", "matched_text": ln["text"],
                "start_offset": ln["start"], "end_offset": ln["end"],
                "explanation": f"OCR read this line with {int(ln['confidence'] * 100)}% confidence. Check the transcription against the image before relying on rule results for it.",
                "source_reference": "OCR engine confidence", "suggested_correction": None, "confidence": ln["confidence"],
                "requires_human_review": True, "finding_source": "ocr",
                "region_json": json.dumps([{"box": ln["box"], "line": i}]),
            })
    return out
