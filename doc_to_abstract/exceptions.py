class DocToAbstractError(Exception):
    """Base exception for doc-to-abstract."""


class ConfigError(DocToAbstractError):
    """Error in configuration file."""


class FileExtractionError(DocToAbstractError):
    """Error reading or extracting text from a file."""


class APIError(DocToAbstractError):
    """Error communicating with Claude API."""
