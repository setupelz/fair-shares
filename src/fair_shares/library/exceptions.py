"""
Exceptions that are used throughout the fair-shares library.

"""

from __future__ import annotations


class MissingOptionalDependencyError(ImportError):
    """
    Raised when an optional dependency is missing

    """

    def __init__(self, callable_name: str, requirement: str) -> None:
        """
        Initialise the error

        Parameters
        ----------
        callable_name
            The name of the callable that requires the dependency

        requirement
            The name of the requirement
        """
        error_msg = f"`{callable_name}` requires {requirement} to be installed"
        super().__init__(error_msg)


class FairSharesError(Exception):
    """Base exception for fair-shares library."""

    pass


class ConfigurationError(FairSharesError):
    """Raised when configuration is invalid or missing."""

    pass


class DataError(FairSharesError):
    """Base exception for data-related errors."""

    pass


class DataLoadingError(DataError):
    """Raised when data files cannot be loaded."""

    pass


class DataProcessingError(DataError):
    """Raised when data doesn't meet requirements."""

    pass


class AllocationError(FairSharesError):
    """Raised when fair share calculations fail."""

    pass


class IAMCDataError(DataError):
    """Raised when IAMC data operations fail."""

    pass


class ValidationError(FairSharesError):
    """Base exception for validation errors."""

    pass


class InputValidationError(ValidationError):
    """
    Raised when input validation fails.

    Input validation includes checking data structure, value ranges,
    required fields, and year coverage before running allocations.
    """

    pass


class OutputValidationError(ValidationError):
    """
    Raised when output validation fails.

    Output validation includes checking that shares sum to 1.0,
    no unexpected null values exist, and data structure is correct.
    """

    pass
