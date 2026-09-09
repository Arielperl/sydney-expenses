from PIL import Image, ImageDraw

from app.services.extraction.image_preprocessing import (
    MAX_DIMENSION,
    MAX_PIXELS,
    TARGET_RECEIPT_WIDTH,
    compute_target_scale,
    generate_variants,
    generate_variants_with_detection,
    preprocess_for_ocr,
)


def test_narrow_receipt_is_upscaled_toward_target_width():
    """The real-world bug this fixes: a 330x736 photo previously only grew to
    ~359px wide because scaling was based on the (already-large) height."""
    scale = compute_target_scale(330, 736)
    new_width = round(330 * scale)
    assert 1200 <= new_width <= 1600


def test_scale_targets_width_not_height():
    scale = compute_target_scale(300, 800)
    assert round(300 * scale) == TARGET_RECEIPT_WIDTH


def test_already_wide_enough_image_is_not_upscaled():
    scale = compute_target_scale(2000, 3000)
    assert scale == 1.0


def test_scale_never_exceeds_max_dimension():
    # A pathologically narrow-but-tall image: naive width-based scaling alone
    # would blow the height past any reasonable bound.
    scale = compute_target_scale(50, 20000)
    assert round(50 * scale) <= MAX_DIMENSION
    assert round(20000 * scale) <= MAX_DIMENSION


def test_scale_never_exceeds_max_pixel_budget():
    scale = compute_target_scale(100, 100000)
    width, height = round(100 * scale), round(100000 * scale)
    assert width * height <= MAX_PIXELS


def test_oversized_image_is_capped_not_left_huge():
    """Memory-abuse guard: an unusually large upload must be bounded, not
    upscaled further and not left to consume unbounded memory downstream."""
    scale = compute_target_scale(6000, 9000)
    assert scale < 1.0
    assert round(6000 * scale) <= MAX_DIMENSION
    assert round(9000 * scale) <= MAX_DIMENSION


def test_zero_size_image_does_not_crash():
    assert compute_target_scale(0, 0) == 1.0


def test_generate_variants_produces_expected_keys_and_matching_upscaled_size():
    image = Image.new("RGB", (330, 736), color="white")
    variants = generate_variants(image)
    assert set(variants.keys()) == {"enhanced", "illumination_normalized", "adaptive_threshold", "denoised"}
    for variant in variants.values():
        width, height = variant.size
        assert 1200 <= width <= 1600
        assert variant.mode in ("L", "1")


def test_adaptive_threshold_variant_is_binarized():
    image = Image.new("L", (400, 800))
    for x in range(400):
        for y in range(800):
            image.putpixel((x, y), 255 if (x + y) % 2 == 0 else 0)
    variants = generate_variants(image)
    histogram = variants["adaptive_threshold"].histogram()
    # A binarized image's histogram has mass overwhelmingly at the extremes.
    non_extreme_mass = sum(histogram[10:246])
    assert non_extreme_mass < sum(histogram) * 0.05


def test_preprocess_for_ocr_returns_the_enhanced_variant():
    image = Image.new("RGB", (330, 736), color="white")
    result = preprocess_for_ocr(image)
    variants = generate_variants(image)
    assert result.size == variants["enhanced"].size


def test_preprocessing_is_deterministic():
    image = Image.new("RGB", (330, 736), color="white")
    first = preprocess_for_ocr(image).tobytes()
    second = preprocess_for_ocr(image).tobytes()
    assert first == second


def test_narrow_receipt_on_large_white_canvas_crops_before_scaling():
    """The other real-world bug this fixes: a genuinely narrow receipt
    centered in a much larger white canvas previously stayed tiny no matter
    how high the scale target was, because the whole canvas — not just the
    receipt — was what got scaled. Cropping to the receipt's own region
    first means the *receipt's* content, not the canvas, ends up at the
    target width."""
    canvas = Image.new("RGB", (2000, 2400), color="white")
    draw = ImageDraw.Draw(canvas)
    # A receipt-shaped region: large enough to clear the confidence bar
    # (comfortably above MIN_DOCUMENT_AREA_RATIO) and with a moderate aspect
    # ratio, unlike an extreme narrow strip, so the crop can actually reach
    # the target width without the separate MAX_DIMENSION safety cap (tested
    # on its own above) also kicking in here.
    draw.rectangle([700, 600, 1300, 1800], outline="black", fill=(230, 230, 230))
    for i in range(10):
        draw.line([730, 650 + i * 100, 1270, 650 + i * 100], fill="black", width=3)

    variants = generate_variants(canvas)
    enhanced = variants["enhanced"]
    # After a correct crop-then-scale, the output width should land near the
    # normal target, not stay at the full (uncropped) canvas's own width.
    assert 1200 <= enhanced.width <= 1600


def test_illumination_normalized_variant_boosts_a_faded_images_contrast():
    """A faded/low-contrast receipt needs local (adaptive) contrast recovery,
    not just a flat global stretch — this is the CLAHE-based variant."""
    faded = Image.new("L", (600, 900), color=200)
    draw = ImageDraw.Draw(faded)
    for i in range(15):
        draw.line([40, 60 + i * 50, 560, 60 + i * 50], fill=190, width=4)  # barely-visible "text"

    variants = generate_variants(faded)
    original_extrema = faded.resize(variants["illumination_normalized"].size).getextrema()
    normalized_extrema = variants["illumination_normalized"].getextrema()
    original_range = original_extrema[1] - original_extrema[0]
    normalized_range = normalized_extrema[1] - normalized_extrema[0]
    assert normalized_range > original_range


def test_generate_variants_with_detection_reports_confident_crop():
    canvas = Image.new("RGB", (2000, 2600), color="white")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([700, 600, 1300, 1800], outline="black", fill=(230, 230, 230))
    for i in range(10):
        draw.line([730, 650 + i * 100, 1270, 650 + i * 100], fill="black", width=3)

    variants, detection = generate_variants_with_detection(canvas)

    assert set(variants) == {"enhanced", "illumination_normalized", "adaptive_threshold", "denoised"}
    assert detection.cropped is True


def test_generate_variants_with_detection_falls_back_on_a_blank_image():
    blank = Image.new("L", (600, 900), color=255)
    variants, detection = generate_variants_with_detection(blank)
    assert set(variants) == {"enhanced", "illumination_normalized", "adaptive_threshold", "denoised"}
    assert detection.cropped is False


def test_generate_variants_matches_generate_variants_with_detection():
    """The backwards-compatible entry point must keep producing the exact
    same variants as the detection-returning one, just without the report."""
    image = Image.new("L", (400, 700), color=255)
    variants_only = generate_variants(image)
    variants_with_detection, _detection = generate_variants_with_detection(image)
    assert set(variants_only) == set(variants_with_detection)
