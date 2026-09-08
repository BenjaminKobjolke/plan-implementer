"""Application-specific exception types."""


class PlanImplementerError(Exception):
    """Base class for expected application errors."""


class ConfigurationError(PlanImplementerError):
    """Raised when input, settings, or the plan folder cannot be validated."""


class OperationalError(PlanImplementerError):
    """Raised when an external operation cannot be completed."""
