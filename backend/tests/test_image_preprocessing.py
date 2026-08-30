from PIL import Image

from app.services.extraction.image_preprocessing import (
    MAX_DIMENSION,
    MAX_PIXELS,
    TARGET_RECEIPT_WIDTH,
    compute_target_scale,
    generate_variants,
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
    assert set(variants.keys()) == {"enhanced", "denoised", "threshold"}
    for variant in variants.values():
        width, height = variant.size
        assert 1200 <= width <= 1600
        assert variant.mode in ("L", "1")


def test_threshold_variant_is_binarized():
    image = Image.new("L", (400, 800))
    for x in range(400):
        for y in range(800):
            image.putpixel((x, y), 255 if (x + y) % 2 == 0 else 0)
    variants = generate_variants(image)
    histogram = variants["threshold"].histogram()
    # A binarized image's histogram has mass only at the extremes.
    non_extreme_mass = sum(histogram[10:246])
    assert non_extreme_mass == 0


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
