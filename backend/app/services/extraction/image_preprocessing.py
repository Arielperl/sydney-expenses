"""Prepares a receipt photo for Tesseract OCR.

Operates entirely in memory on a `PIL.Image` and returns `PIL.Image` objects —
no temporary files are ever created here. The original verified upload on disk
is never modified; callers keep using it (e.g. for the vision model) alongside
these preprocessed copies used only for OCR.

Two compounding problems this addresses, found by diagnosing real uploads:

1. Scaling based on `max(width, height)` is wrong for a typical receipt photo:
   receipts are much taller than wide, so height clears most thresholds while
   width — the dimension that determines how many pixels each character
   stroke gets — stays tiny. Worse: several real uploads contain a genuinely
   narrow receipt centered inside a much larger white/uniform canvas, so even
   width-based scaling of the *whole photo* still leaves the receipt's own
   text tiny relative to the target. `document_geometry.detect_and_correct_document`
   now crops to the receipt's own region *first* (falling back safely to the
   original image when detection isn't confident), so the width-based scale
   below always targets the receipt's actual content.
2. A single global (Otsu) threshold or a flat contrast boost does not cope
   with an unevenly lit or genuinely faded receipt — the "enhanced"/CLAHE
   variants below use local (adaptive) contrast normalization instead, which
   is far more robust to uneven illumination and fading.
"""

from PIL import Image, ImageFilter, ImageOps

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover - opencv-python-headless/numpy are declared dependencies
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]

from app.services.extraction.document_geometry import DocumentDetection, detect_and_correct_document

TARGET_RECEIPT_WIDTH = 1400
MAX_DIMENSION = 4000
MAX_PIXELS = 15_000_000
CONTRAST_CUTOFF = 1  # ImageOps.autocontrast: percent of histogram clipped at each end


def compute_target_scale(width: int, height: int) -> float:
    """Returns the scale factor to apply to a `width` x `height` image.

    Narrow images are scaled up toward `TARGET_RECEIPT_WIDTH` (preserving aspect
    ratio); any image — narrow or already large — is then capped so neither
    dimension exceeds `MAX_DIMENSION` and the total pixel count never exceeds
    `MAX_PIXELS`, which bounds memory/CPU use regardless of the input size.
    """
    if width <= 0 or height <= 0:
        return 1.0

    scale = TARGET_RECEIPT_WIDTH / width if width < TARGET_RECEIPT_WIDTH else 1.0

    max_scale_for_dimension = min(MAX_DIMENSION / width, MAX_DIMENSION / height)
    scale = min(scale, max_scale_for_dimension)

    max_scale_for_pixels = (MAX_PIXELS / (width * height)) ** 0.5
    scale = min(scale, max_scale_for_pixels)

    return max(scale, 0.01)


def _upscale_grayscale(corrected: Image.Image) -> Image.Image:
    grayscale = ImageOps.grayscale(corrected)
    width, height = grayscale.size
    scale = compute_target_scale(width, height)
    if scale != 1.0:
        new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
        # LANCZOS for downscaling (rare; only for abnormally large uploads),
        # BICUBIC for upscaling — a smoother interpolation that is less likely
        # to introduce ringing artifacts around thin Hebrew character strokes
        # than LANCZOS tends to at large upscale factors.
        resample = Image.LANCZOS if scale < 1.0 else Image.BICUBIC
        grayscale = grayscale.resize(new_size, resample)
    return grayscale


def _cropped_and_scaled(image: Image.Image) -> tuple[Image.Image, DocumentDetection]:
    """The shared starting point for every variant below: crop to the
    detected document region (falls back to the original image untouched if
    detection isn't confident), correct EXIF orientation, then grayscale and
    width-based upscale."""
    cropped, detection = detect_and_correct_document(image)
    corrected = ImageOps.exif_transpose(cropped) or cropped
    return _upscale_grayscale(corrected), detection


def _otsu_threshold(image: Image.Image) -> int:
    """Computes a global Otsu threshold from the image's own histogram — no
    numpy dependency needed, since this only ever iterates the 256-bin
    grayscale histogram, not the pixels themselves. Used only as the fallback
    when cv2 (which provides adaptive thresholding) is unavailable."""
    histogram = image.histogram()
    total = sum(histogram)
    if total == 0:
        return 128

    sum_all = sum(i * count for i, count in enumerate(histogram))
    sum_background = 0.0
    weight_background = 0
    best_variance = -1.0
    best_threshold = 128

    for threshold, count in enumerate(histogram):
        weight_background += count
        if weight_background == 0:
            continue
        weight_foreground = total - weight_background
        if weight_foreground == 0:
            break
        sum_background += threshold * count
        mean_background = sum_background / weight_background
        mean_foreground = (sum_all - sum_background) / weight_foreground
        variance = weight_background * weight_foreground * (mean_background - mean_foreground) ** 2
        if variance > best_variance:
            best_variance = variance
            best_threshold = threshold

    return best_threshold


def _clahe_normalize(grayscale: Image.Image) -> Image.Image:
    """Local (tile-based) contrast normalization — far more robust than a
    single flat autocontrast/brightness adjustment for a receipt that is
    unevenly lit or genuinely faded, since each region of the image gets its
    own local contrast stretch rather than one global one. Falls back to
    plain autocontrast if cv2 is unavailable."""
    if cv2 is None or np is None:
        return ImageOps.autocontrast(grayscale, cutoff=CONTRAST_CUTOFF)
    array = np.array(grayscale)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    return Image.fromarray(clahe.apply(array))


def _adaptive_threshold(grayscale: Image.Image) -> Image.Image:
    """Locally-adaptive binarization — unlike a single global (Otsu)
    threshold, this copes with a receipt whose illumination varies across
    the page (a common cause of a "faded" look), by thresholding each
    neighborhood against its own local mean rather than one page-wide
    cutoff. Falls back to global Otsu thresholding if cv2 is unavailable."""
    if cv2 is None or np is None:
        threshold_value = _otsu_threshold(grayscale)
        return grayscale.point(lambda p, t=threshold_value: 255 if p > t else 0)
    array = np.array(grayscale)
    block_size = max(11, (min(array.shape) // 20) | 1)  # odd, scales with image size
    binarized = cv2.adaptiveThreshold(
        array, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, 10
    )
    return Image.fromarray(binarized)


def generate_variants_with_detection(image: Image.Image) -> tuple[dict[str, Image.Image], DocumentDetection]:
    """Produces a small, bounded set of deterministic preprocessing variants to
    try OCR against, alongside the `DocumentDetection` report from the shared
    crop step — callers that need to know whether cropping was confident
    (e.g. to decide which single image to send a vision model) use this
    instead of the detection-discarding `generate_variants` below.

    Kept intentionally short (4 variants) so the bounded OCR scoring strategy
    in `ocr_selection.py` runs a fixed, small number of Tesseract calls rather
    than an unbounded cross-product.

    - "enhanced": grayscale + crop-to-document + width-based upscale +
      autocontrast + a mild sharpen. The default, safest for preserving thin
      Hebrew strokes.
    - "illumination_normalized": the same crop/scale, but with local (CLAHE)
      contrast normalization instead of one flat autocontrast — targets a
      faded or unevenly lit receipt specifically.
    - "adaptive_threshold": locally-adaptive binarization, which copes with
      uneven illumination far better than one global threshold. Binarization
      can still destroy thin strokes on a *clean* receipt, so it is offered
      only as one scored candidate among several, never the default.
    - "denoised": adds a light median filter before sharpening, which helps on
      photos with camera-sensor noise/JPEG artifacts, at some risk of
      softening the thinnest strokes — evaluated as an alternative, not a
      replacement.
    """
    grayscale, detection = _cropped_and_scaled(image)

    enhanced = ImageOps.autocontrast(grayscale, cutoff=CONTRAST_CUTOFF)
    sharpened = enhanced.filter(ImageFilter.SHARPEN)

    illumination_normalized = _clahe_normalize(grayscale).filter(ImageFilter.SHARPEN)

    adaptive_thresholded = _adaptive_threshold(enhanced)

    denoised = enhanced.filter(ImageFilter.MedianFilter(size=3))
    denoised = denoised.filter(ImageFilter.SHARPEN)

    variants = {
        "enhanced": sharpened,
        "illumination_normalized": illumination_normalized,
        "adaptive_threshold": adaptive_thresholded,
        "denoised": denoised,
    }
    return variants, detection


def generate_variants(image: Image.Image) -> dict[str, Image.Image]:
    """Backwards-compatible entry point for callers that only need the
    preprocessing variants, not the crop-detection report."""
    variants, _detection = generate_variants_with_detection(image)
    return variants


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    """Backwards-compatible single-image entry point (the default "enhanced"
    variant) for callers that don't need the bounded multi-variant/multi-PSM
    OCR selection strategy."""
    return generate_variants(image)["enhanced"]
