"""Detects and crops the receipt/document region out of a photo, correcting
small skew and perspective when a reliable document boundary is found.

The concrete failure this targets: several real uploads contain a narrow
receipt centered in a much larger white/uniform canvas or background. Scaling
the *whole* photo (the previous behavior) leaves the actual receipt text tiny
relative to the target OCR width, no matter how high that target is. Cropping
to the document's own bounding region *before* scaling fixes this directly.

The crop region is the union bounding box of every sufficiently large dark
region in the frame, not just the single largest one. A real receipt photo's
printed content is naturally many separate blobs (one per line of text, with
white space between them) rather than one solid block — trusting only the
single largest contour was found, on real photos, to crop down to just a
dense header/logo region while cutting off the rest of the receipt entirely.
The union of all significant contours' bounding boxes reliably captures the
receipt's full printed extent regardless of how fragmented the text is.

Every step here is bounded and defensive:
- Geometry detection always runs on a small, capped working copy (never the
  full-resolution image), so CPU/memory cost never scales with upload size.
- A crop/deskew/perspective correction is only ever applied when the detected
  region clears an explicit confidence bar; otherwise this returns the
  original image completely untouched. A wrong crop is far worse than no
  crop — OCR can still read a merely-small receipt, but not a receipt that
  was cropped out of the frame.
- Any cv2/numpy exception here is caught and treated as "no confident
  detection", never propagated — geometry detection is best-effort, and a
  bug here must never break the extraction pipeline as a whole.
"""

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps

try:
    import cv2
except ImportError:  # pragma: no cover - opencv-python-headless is a declared dependency
    cv2 = None  # type: ignore[assignment]

# Geometry detection always runs on a working copy capped to this size —
# bounds contour-finding cost regardless of the original upload's resolution.
MAX_DETECTION_DIMENSION = 1600

# A detected region must cover at least this fraction of the frame to be
# treated as "the document" rather than noise (a shadow, a logo, a stray
# mark) — and no more than this fraction, since a region covering nearly the
# entire frame means there is no meaningful margin to crop away at all.
MIN_DOCUMENT_AREA_RATIO = 0.06
MAX_DOCUMENT_AREA_RATIO = 0.97

# A single contour is only trusted for perspective correction (a genuine
# document quadrilateral, e.g. one with a visible border/edge) when it
# accounts for most of the union bounding box's own area — i.e. one
# coherent region actually dominates, rather than the union being an
# aggregate of many small, separate text blobs (the common case for a plain
# receipt photo with no visible border).
MIN_DOMINANT_CONTOUR_SHARE = 0.7
MIN_PERSPECTIVE_AREA_RATIO = 0.15

# Individual contours smaller than this fraction of the frame are treated as
# noise (a stray mark, a JPEG artifact) and excluded from the union — without
# this, a handful of speckles far from the real content could inflate the
# union bounding box arbitrarily.
MIN_CONTOUR_AREA_RATIO = 0.0004

CROP_PADDING_RATIO = 0.02  # small margin kept around a detected crop box


@dataclass(frozen=True)
class DocumentDetection:
    """Reports what was actually done, purely for tests/diagnostics — never
    exposed via the API."""

    cropped: bool = False
    deskewed: bool = False
    perspective_corrected: bool = False
    confidence: float = 0.0


def _document_mask(gray: np.ndarray):
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = np.ones((15, 15), np.uint8)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def _significant_contours(contours, frame_area: float):
    min_area = frame_area * MIN_CONTOUR_AREA_RATIO
    return [c for c in contours if cv2.contourArea(c) >= min_area]


def _union_bounding_rect(contours) -> tuple[int, int, int, int]:
    all_points = np.vstack(contours)
    return cv2.boundingRect(all_points)


def _order_quad_points(pts: np.ndarray) -> np.ndarray:
    """Orders 4 points as top-left, top-right, bottom-right, bottom-left —
    the order cv2.getPerspectiveTransform's destination rectangle expects."""
    ordered = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    ordered[0] = pts[np.argmin(s)]
    ordered[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1).flatten()
    ordered[1] = pts[np.argmin(diff)]
    ordered[3] = pts[np.argmax(diff)]
    return ordered


def _perspective_correct(image: Image.Image, quad: np.ndarray) -> Image.Image | None:
    quad = _order_quad_points(quad)
    (tl, tr, br, bl) = quad
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    out_width = max(int(width_a), int(width_b))
    out_height = max(int(height_a), int(height_b))
    if out_width < 20 or out_height < 20:
        return None

    dest = np.array(
        [[0, 0], [out_width - 1, 0], [out_width - 1, out_height - 1], [0, out_height - 1]],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(quad, dest)
    source = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    warped = cv2.warpPerspective(source, matrix, (out_width, out_height), borderValue=(255, 255, 255))
    return Image.fromarray(cv2.cvtColor(warped, cv2.COLOR_BGR2RGB))


def _crop_with_padding(image: Image.Image, x: int, y: int, w: int, h: int) -> Image.Image:
    pad_x = round(w * CROP_PADDING_RATIO)
    pad_y = round(h * CROP_PADDING_RATIO)
    left = max(0, x - pad_x)
    top = max(0, y - pad_y)
    right = min(image.width, x + w + pad_x)
    bottom = min(image.height, y + h + pad_y)
    if right <= left or bottom <= top:
        return image
    return image.crop((left, top, right, bottom))


def _detect_region(gray: np.ndarray, frame_area: float):
    """Returns (significant_contours, union_bbox, union_area_ratio) or None
    if nothing clears the confidence bar."""
    mask = _document_mask(gray)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    significant = _significant_contours(contours, frame_area)
    if not significant:
        return None

    bbox = _union_bounding_rect(significant)
    _, _, w, h = bbox
    area_ratio = (w * h) / frame_area if frame_area else 0.0
    if area_ratio < MIN_DOCUMENT_AREA_RATIO or area_ratio > MAX_DOCUMENT_AREA_RATIO:
        return None

    return significant, bbox, area_ratio


def detect_and_correct_document(image: Image.Image) -> tuple[Image.Image, DocumentDetection]:
    """Best-effort: crops to the detected document region (the union of every
    significant dark region in the frame), deskews small rotations, and
    applies a perspective correction when one contour clearly dominates and
    approximates a confident quadrilateral. Returns the original image,
    untouched, whenever detection isn't confident enough or anything goes
    wrong."""
    if cv2 is None:
        return image, DocumentDetection()

    width, height = image.size
    if width <= 0 or height <= 0:
        return image, DocumentDetection()

    try:
        corrected = ImageOps.exif_transpose(image) or image
        detect_scale = min(1.0, MAX_DETECTION_DIMENSION / max(corrected.width, corrected.height))
        detect_size = (
            max(1, round(corrected.width * detect_scale)),
            max(1, round(corrected.height * detect_scale)),
        )
        small = corrected.resize(detect_size, Image.BILINEAR) if detect_scale < 1.0 else corrected
        gray = np.array(ImageOps.grayscale(small))
        frame_area = float(detect_size[0] * detect_size[1])

        detected = _detect_region(gray, frame_area)
        if detected is None:
            return corrected, DocumentDetection()
        significant, (x, y, w, h), area_ratio = detected

        # A confident 4-point quadrilateral is only attempted when one
        # contour clearly dominates the union (a genuine bordered document),
        # not when the union is an aggregate of many separate text blobs.
        if area_ratio >= MIN_PERSPECTIVE_AREA_RATIO:
            largest = max(significant, key=cv2.contourArea)
            largest_area = cv2.contourArea(largest)
            union_area = float(w * h)
            if union_area > 0 and (largest_area / union_area) >= MIN_DOMINANT_CONTOUR_SHARE:
                peri = cv2.arcLength(largest, True)
                approx = cv2.approxPolyDP(largest, 0.02 * peri, True)
                if len(approx) == 4 and cv2.isContourConvex(approx):
                    full_res_quad = approx.reshape(4, 2).astype("float32") / detect_scale
                    warped = _perspective_correct(corrected, full_res_quad)
                    if warped is not None:
                        return warped, DocumentDetection(
                            cropped=True, perspective_corrected=True, confidence=round(area_ratio, 3)
                        )

        # No confident quadrilateral — check for skew via the union's own
        # minimum-area rotated rect, then crop to the union bbox at full
        # resolution (recomputed post-rotation if we did deskew).
        union_points = np.vstack(significant)
        rect = cv2.minAreaRect(union_points)
        angle = rect[2]
        # cv2's angle convention varies by version/orientation; normalize to
        # a small signed skew in (-45, 45) so a near-axis-aligned box (the
        # common case) is never rotated by a spurious ~90 degrees.
        if angle < -45:
            angle += 90
        elif angle > 45:
            angle -= 90

        working = corrected
        deskewed = False
        if 0.5 < abs(angle) < 20:
            working = corrected.rotate(-angle, resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))
            deskewed = True
            # Re-run detection once on the deskewed image to get an accurate
            # crop box post-rotation — bounded to exactly one extra pass,
            # never recursive.
            working_detect_size = (
                max(1, round(working.width * detect_scale)),
                max(1, round(working.height * detect_scale)),
            )
            working_small = (
                working.resize(working_detect_size, Image.BILINEAR) if detect_scale < 1.0 else working
            )
            gray2 = np.array(ImageOps.grayscale(working_small))
            redetected = _detect_region(gray2, float(working_detect_size[0] * working_detect_size[1]))
            if redetected is not None:
                _, (x, y, w, h), area_ratio = redetected

        scale_back = 1.0 / detect_scale
        crop_box = (round(x * scale_back), round(y * scale_back), round(w * scale_back), round(h * scale_back))
        result = _crop_with_padding(working, *crop_box)
        return result, DocumentDetection(cropped=True, deskewed=deskewed, confidence=round(area_ratio, 3))
    except Exception:  # noqa: BLE001 - detection is best-effort; any failure falls back to the original image
        return image, DocumentDetection()
