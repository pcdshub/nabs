import inspect
from typing import Any, Callable, Dict, Union

from ophyd.signal import DerivedSignal, SignalRO


class InvertedSignal(DerivedSignal):
    """
    Invert another `ophyd` Signal

    Parameters
    ----------
    derived_from: `ophyd.signal.Signal`
        Ophyd Signal
    """
    def __init__(self, derived_from, *, name=None, **kwargs):
        # Create a name if None is given
        if not name:
            name = derived_from.name + '_inverted'
        # Initialize the DerivedSignal
        super().__init__(derived_from, name=name, **kwargs)

    def forward(self, value):
        """Invert the value"""
        return -value

    def inverse(self, value):
        """Invert the value"""
        return -value

    def trigger(self):
        return self.derived_from.trigger()


class ErrorSignal(SignalRO, DerivedSignal):
    """
    Signal that reports the absolute error from a provided target

    Parameters
    ----------
    derived_from : `ophyd.signal.Signal`

    target : float
        Position of zero error
    """
    def __init__(self, derived_from, target, *, name=None, **kwargs):
        # Create a name if None is given
        if not name:
            name = derived_from.name + '_error'
        # Store the target
        self.target = target
        # Initialize the DerivedSignal
        super().__init__(derived_from, name=name, **kwargs)

    def forward(self, value):
        """Invert the value"""
        return NotImplemented

    def inverse(self, value):
        """Invert the value"""
        return abs(value - self.target)

    def trigger(self):
        return self.derived_from.trigger()


def add_named_kwargs_to_signature(
    func_or_signature: Union[inspect.Signature, Callable],
    kwargs: Dict[str, Any]
) -> inspect.Signature:
    """
    Add named keyword arguments with default values to a function signature.

    Parameters
    ----------
    func_or_signature : inspect.Signature or callable
        The function or signature.

    kwargs : dict
        The dictionary of kwarg_name to default_value.

    Returns
    -------
    modified_signature : inspect.Signature
        The modified signature with additional keyword arguments.
    """

    if isinstance(func_or_signature, inspect.Signature):
        sig = func_or_signature
    else:
        sig = inspect.signature(func_or_signature)

    params = list(sig.parameters.values())
    keyword_only_indices = [
        idx for idx, param in enumerate(params)
        if param.kind == inspect.Parameter.KEYWORD_ONLY
    ]
    if not keyword_only_indices:
        start_params, end_params = params, []
    else:
        insert_at = keyword_only_indices[0]
        start_params, end_params = params[:insert_at], params[insert_at:]

    wrapper_params = list(
        inspect.Parameter(
            name, kind=inspect.Parameter.KEYWORD_ONLY, default=value
        )
        for name, value in kwargs.items()
        if name not in sig.parameters
    )

    return sig.replace(parameters=start_params + wrapper_params + end_params)
