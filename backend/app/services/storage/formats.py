"""Shared, provider-independent mapping from a Pillow-verified image format to a
safe extension/content-type. Used by both storage backends so a server-generated
object key is always derived from the verified bytes, never a client-supplied
filename or content type."""

EXTENSION_BY_VERIFIED_FORMAT = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}

CONTENT_TYPE_BY_VERIFIED_FORMAT = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
