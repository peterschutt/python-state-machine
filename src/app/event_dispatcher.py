import logging
from collections import abc
from enum import Enum
from typing import Any, ClassVar

import attr

from .model import EventData, Model

HandlerType = abc.Callable[["EventType"], None]
KeyType = tuple[str, ...]


class States(str, Enum):
    dispatching = "dispatching"
    handled = "handled"
    dropped = "dropped"


@attr.s(auto_detect=True)
class EventType:
    event: KeyType = attr.ib()
    ctx: dict[str, Any] = attr.ib()

    @classmethod
    def new(
        cls, event: str, ctx: dict[str, Any], event_delimiter: str = ":"
    ) -> "EventType":
        """
        Create an EventType.

        >>> EventType.new("a:b:c", {"some": "context"})
        EventType(event=('a', 'b', 'c'), ctx={'some': 'context'})
        >>> EventType.new("a.b.c", {"some": "context"}, event_delimiter=".")
        EventType(event=('a', 'b', 'c'), ctx={'some': 'context'})

        Parameters
        ----------
        event : str
            The delimited string representation of an external event.
        ctx : str
            The context or body of the external event.
        event_delimiter : str
            The separator used to delimit the event string, default ":".

        Returns
        -------
        EventType
        """
        event_tuple = tuple(event.split(event_delimiter))
        return cls(event=event_tuple, ctx=ctx)


@attr.s(auto_detect=True)
class DispatcherContext:
    event: EventType | None = attr.ib(default=None)
    handler: HandlerType | None = attr.ib(default=None)


@attr.s(auto_detect=True)
class Dispatcher(Model):
    """
    Instance is callable and expects to receive an `str` event key and a mapping of
    event context.

    Dispatches the event to a handler if it exists, otherwise drops the event.

        >>> dispatcher = Dispatcher.new()
        >>> dispatcher.state
        <States.invoked: 'invoked'>
        >>> dispatcher.ctx
        DispatcherContext(event=None, handler=None)
        >>> event = EventType(event=("a", "b", "c"), ctx={"some": "context"})
        >>> dispatcher(event)
        >>> dispatcher.state
        <States.dropped: 'dropped'>
        >>> dispatcher = Dispatcher.new()
        >>> dispatcher.register_handler(("a", "b"), lambda e: print("handled by 'a:b' handler"))
        >>> dispatcher(event)
        handled by 'a:b' handler
        >>> dispatcher = Dispatcher.new()
        >>> dispatcher.register_handler(("a", "b"), lambda e: print("handled by 'a:b' handler"))
        >>> dispatcher.register_handler(("a", "b", "c"), lambda e: print("handled by 'a:b:c' handler"))
        >>> dispatcher(event)
        handled by 'a:b:c' handler
        >>> dispatcher.state
        <States.handled: 'handled'>
        >>> dispatcher = Dispatcher.new()
        >>> dispatcher.register_handler(("a", "b", "c"), lambda e: 1 / 0)
        >>> dispatcher(event)
        >>> dispatcher.state
        <States.error: 'error'>
    """

    _handlers: ClassVar[dict[KeyType, HandlerType]] = {}

    ctx: DispatcherContext = attr.ib(default=attr.Factory(DispatcherContext))

    @classmethod
    def new(cls, *args: Any, **kwargs: Any) -> "Dispatcher":
        """
        Create a new Dispatcher object.

        Parameters
        ----------
        args : Any
        kwargs : Any

        Returns
        -------
        Dispatcher
        """
        inst = super().new(*args, **kwargs)
        inst.add_states(States)
        inst.add_transitions(
            [
                {
                    "trigger": "dispatch_event",
                    "source": "invoked",
                    "dest": "dispatching",
                },
                {"trigger": "handle", "source": "dispatching", "dest": "handled"},
                {"trigger": "drop", "source": "dispatching", "dest": "dropped"},
                {"trigger": "error", "source": "*", "dest": "error"},
            ]
        )
        return inst

    @classmethod
    def register_handler(cls, key: KeyType, handler: HandlerType) -> None:
        """
        Registers a handler to the instance.

        Parameters
        ----------
        key : KeyType
        handler : HandlerType
        """
        cls._handlers[key] = handler

    @classmethod
    def deregister_handler(cls, key: KeyType) -> None:
        del cls._handlers[key]

    @classmethod
    def has_handler(cls, key: KeyType) -> bool:
        """
        `True` if handler registered for given key, else `False`.

        Parameters
        ----------
        key : KeyType

        Returns
        -------
        bool
        """
        return key in cls._handlers

    def find_handler(self, event: EventType) -> HandlerType | None:
        """
        Find a handler for a given event.

        Returns the handler registered to the longest key matching the `event`.

            >>> Dispatcher.register_handler(("b", "c"), lambda e: print("handled by 'b:c' handler"))
            >>> dispatcher = Dispatcher.new()
            >>> event = EventType(event=("b", "c", "d"), ctx={"some": "context"})
            >>> dispatcher(event)
            handled by 'b:c' handler
            >>> Dispatcher.register_handler(("b", "c", "d"), lambda e: print("handled by 'b:c:d' handler"))
            >>> dispatcher = Dispatcher.new()
            >>> dispatcher(event)
            handled by 'b:c:d' handler

        Parameters
        ----------
        event : EventType

        Returns
        -------
        HandlerType | None
        """
        possible_keys = {event.event[: i + 1] for i in range(len(event.event))}
        possible_handler_keys = self._handlers.keys() & possible_keys
        if not possible_handler_keys:
            return None
        longest_handler_key = max(possible_handler_keys, key=len)
        return self._handlers[longest_handler_key]

    def on_enter_dispatching(self, event_data: EventData) -> None:
        """
        Dispatch the event to a registered handler, or drop it.

        Parameters
        ----------
        event_data : EventType

        Returns
        -------

        """
        event = self.ctx.event
        assert event is not None
        self.ctx.handler = handler = self.find_handler(event)
        if handler is not None:
            handler(event)
            self.handle()
        else:
            self.drop()

    def __call__(self, event: EventType) -> None:
        self.ctx.event = event
        self.dispatch_event(log_at=logging.DEBUG)
