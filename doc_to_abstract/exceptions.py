class DocToAbstractError(Exception):
    """Base exception for doc-to-abstract."""


class ConfigError(DocToAbstractError):
    """Error in configuration file."""


class PDFError(DocToAbstractError):
    """Error reading or validating PDF file."""


class APIError(DocToAbstractError):
    """Error communicating with Claude API."""
