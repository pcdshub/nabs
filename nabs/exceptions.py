class NabsError(Exception):
    """Base class for nabs-related errors."""


class DaqNotConfiguredError(NabsError):
    """The DAQ has not yet been configured."""
