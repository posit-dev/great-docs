"""
Errors that stop documentation builds
"""

__all__ = ["BuildError"]


class BuildError(RuntimeError):
    """
    A build failure that leaves no usable site

    The failure is reported in the build log or on standard error before this exception is
    raised. Command-line callers can exit without printing the message again.
    """
