"""K8s config standard exception hierarchy.

Per SAD Section 6.5, all config builder exceptions must be instances of
these types. Validation errors at builder boundaries must use ConfigError.
"""


class K8sConfigError(Exception):
    """Base class for all K8s config system exceptions."""


class ConfigError(K8sConfigError):
    """Raised when a builder receives invalid configuration input."""
