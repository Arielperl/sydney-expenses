class StorageError(Exception):
    """Base class for all receipt-storage failures. Messages on these exceptions
    are always safe to show a user or write to a log — never a secret key, an
    Authorization header, or a raw provider response body."""


class StorageConfigError(StorageError):
    """Required configuration for the selected provider is missing or invalid."""


class StorageUnavailableError(StorageError):
    """The storage provider could not be reached at all (network/connection)."""


class StorageAuthenticationError(StorageError):
    """The storage provider rejected our credentials."""


class StorageNotFoundError(StorageError):
    """The configured bucket, or a requested object, does not exist."""


class StorageUploadError(StorageError):
    """The provider reachable and authenticated, but the upload itself failed."""


class SignedUrlError(StorageError):
    """A viewable/signed URL could not be generated for a stored object."""


class StorageDeleteError(StorageError):
    """Deleting a stored object failed."""
