from collections import abc
from enum import Enum
from typing import Any, TypedDict, TypeVar

import attr
import cattrs
from structlog.stdlib import get_logger
from transitions import EventData, Machine

from . import config

ModelType = TypeVar("ModelType", bound="Model")

logger = get_logger()


class TransitionDict(TypedDict):
    trigger: str
    source: str | abc.Sequence[str]
    dest: str | abc.Sequence[str]


class States(str, Enum):
    invoked = "invoked"
    error = "error"


@attr.s(auto_detect=True)
class Model(Machine):
    """
    Base model for the Models as Machines pattern.

    Models must inherit from this machine and follow the following rules:
    - Model types must at least add one `State`
    - Model types must add two `Transition` objects:
        1. from `states.invoked` to the sub-models initial state.
        2. from any of the sub-models states to the `states.finished` state.
    - sub-model modifications to the model/machine instance attributes is performed by
      overriding the `Model.new()` method, by calling `super().new()` to retrieve the
      model instance and then using the relevant `transitions.Machine` methods on the
      instance to add new states and transitions, etc.

        >>> model = Model.new()
        >>> model.state
        <States.invoked: 'invoked'>
    """

    @classmethod
    def new(
        cls: type[ModelType],
        transitions: abc.Sequence[TransitionDict] = (
            TransitionDict(trigger="error", source="*", dest="error"),
        ),
        states: type[Enum] = States,
        initial: Enum = States.invoked,
    ) -> ModelType:
        """
        Create a new `Model` instance.

        All instance creation must be performed through this model.

        Parameters
        ----------
        transitions : Sequence[TransitionDict]
        states : type[Enum]
        initial : Enum

        Returns
        -------
        ModelType
        """
        inst = cls()
        Machine.__init__(
            inst,
            send_event=True,
            before_state_change=["log_leaving_state"],
            initial=initial,
            on_exception=["handle_exception"],
            states=states,
            transitions=transitions,
        )
        return inst

    @property
    def converter(self) -> cattrs.Converter:
        return cattrs.Converter()

    def unstructure(self) -> dict[str, Any]:
        """
        Convert the instance to an unstructured representation.

        Returns
        -------
        dict[str, Any]
        """
        try:
            return self.converter.unstructure(self)  # type:ignore[no-any-return]
        except Exception as e:
            logger.exception(str(e))
            return {}

    def log_leaving_state(self, transitions_event: EventData) -> None:
        """
        Log the model immediately before a transition to another state occurs.

        Registered as the `before_state_change` machine callback.

        Parameters
        ----------
        transitions_event : transitions.EventData
        """
        self.log(
            log_event=f"Before transition to '{transitions_event.transition.dest}'",
            log_level=transitions_event.kwargs.get("log_at"),
        )

    def log(
        self, *, log_event: str, log_level: int | None = None, **kwargs: Any
    ) -> None:
        """
        Log the state and context of the model with the given `level` and `log_event`.

        The logged model context is the `dict` retrieved through calling
        `self.unstructure()`, and is merged with `kwargs`.

        Parameters
        ----------
        log_event : str
            Included by structlog as the log record's 'event' key.
        log_level : int
            Default `logging.DEBUG`
        kwargs : Any
            kwargs are merged with the model's context before logging.
        """
        if log_level is None:
            log_level = config.DEFAULT_LOG_SEVERITY

        context = self.unstructure()
        context.update(kwargs)
        log = logger.bind()
        log.log(log_level, log_event, context=context)

    def handle_exception(self, event_data: EventData) -> None:
        """
        In the event of an unhandled exception, transitions the model to `States.error`.

        Parameters
        ----------
        event_data : EventData
        """
        try:
            logger.exception(event_data.error)
        except Exception as e:
            logger.exception(f"Error handling exception: {e}")
            return
        self.error()
