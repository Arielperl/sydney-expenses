"""Prepares a receipt photo for Tesseract OCR.

Operates entirely in memory on a `PIL.Image` and returns `PIL.Image` objects —
no temporary files are ever created here. The original verified upload on disk
is never modified; callers keep using it (e.g. for the vision model) alongside
these preprocessed copies used only for OCR.

The previous version scaled based on `max(width, height)`, which is wrong for a
typical receipt photo: receipts are much taller than they are wide, so the
*height* already clears most thresholds while the *width* — the dimension that
actually determines how many pixels each character stroke gets — stays tiny.
A 330x736 photo, for example, previously only grew to ~359x800 (upscaled
against its already-large height), leaving Hebrew text far too narrow for
Tesseract to read reliably. This version scales primarily off the *width*,
targeting ~1400px for narrow receipts, while still bounding both dimensions and
total pixel count to avoid memory abuse from an unusually large upload.
"""

from PIL import Image, ImageFilter, ImageOps

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


def _base_enhanced(image: Image.Image) -> Image.Image:
    """EXIF-correct, grayscale, width-based upscale, autocontrast. The shared
    starting point for every variant below."""
    corrected = ImageOps.exif_transpose(image) or image
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

    return ImageOps.autocontrast(grayscale, cutoff=CONTRAST_CUTOFF)


def _otsu_threshold(image: Image.Image) -> int:
    """Computes a global Otsu threshold from the image's own histogram — no
    numpy dependency needed, since this only ever iterates the 256-bin
    grayscale histogram, not the pixels themselves."""
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


def generate_variants(image: Image.Image) -> dict[str, Image.Image]:
    """Produces a small, bounded set of deterministic preprocessing variants to
    try OCR against. Kept intentionally short (3 variants) so the bounded OCR
    scoring strategy in `ocr_selection.py` runs a fixed, small number of
    Tesseract calls rather than an unbounded cross-product.

    - "enhanced": grayscale + width-based upscale + autocontrast + a mild
      sharpen. The default, safest for preserving thin Hebrew strokes.
    - "denoised": adds a light median filter before sharpening, which helps on
      photos with camera-sensor noise/JPEG artifacts, at some risk of
      softening the thinnest strokes — evaluated as an alternative, not a
      replacement.
    - "threshold": a global (Otsu) binarization on top of the enhanced image.
      Binarization can destroy thin strokes, so it is offered only as one
      scored candidate among several, never the default.
    """
    enhanced = _base_enhanced(image)
    sharpened = enhanced.filter(ImageFilter.SHARPEN)

    denoised = enhanced.filter(ImageFilter.MedianFilter(size=3))
    denoised = denoised.filter(ImageFilter.SHARPEN)

    threshold_value = _otsu_threshold(enhanced)
    thresholded = enhanced.point(lambda p, t=threshold_value: 255 if p > t else 0)

    return {
        "enhanced": sharpened,
        "denoised": denoised,
        "threshold": thresholded,
    }


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    """Backwards-compatible single-image entry point (the default "enhanced"
    variant) for callers that don't need the bounded multi-variant/multi-PSM
    OCR selection strategy."""
    return generate_variants(image)["enhanced"]
