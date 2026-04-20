from __future__ import annotations


class DataProviderError(RuntimeError):
    pass


class SourceRateLimitedError(DataProviderError):
    pass


class SourceRequiresApiKeyError(DataProviderError):
    pass


class SourceRequiresLicenseError(DataProviderError):
    pass


class SourceRequiresSubscriptionError(DataProviderError):
    pass
