"""Prepares a receipt photo for Tesseract OCR.

Operates entirely in memory on a `PIL.Image` and returns a `PIL.Image` — no
temporary files are ever created here, so there is nothing to clean up on
success or failure. The original verified upload on disk is never modified;
callers should keep using it (e.g. for the vision model) alongside this
preprocessed copy used only for OCR.

Deliberately mild: grayscale, a contrast boost, a mild sharpen, and upscaling
only when the image is genuinely small. No binarization/thresholding, which
tends to destroy the fine strokes of Hebrew characters at typical receipt-photo
resolutions.
"""

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

MIN_DIMENSION_FOR_OCR = 800
CONTRAST_FACTOR = 1.4


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    corrected = ImageOps.exif_transpose(image) or image
    grayscale = ImageOps.grayscale(corrected)

    width, height = grayscale.size
    if max(width, height) > 0 and max(width, height) < MIN_DIMENSION_FOR_OCR:
        scale = MIN_DIMENSION_FOR_OCR / max(width, height)
        grayscale = grayscale.resize((round(width * scale), round(height * scale)), Image.LANCZOS)

    contrasted = ImageEnhance.Contrast(grayscale).enhance(CONTRAST_FACTOR)
    return contrasted.filter(ImageFilter.SHARPEN)
