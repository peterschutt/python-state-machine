import random
from collections import abc
from enum import Enum

import attr
from transitions import EventData

from .event_dispatcher import EventType
from .model import Model, TransitionDict


class States(str, Enum):
    asleep = "asleep"
    hanging_out = "hanging_out"
    hunting = "hunting"
    eating = "eating"
    error = "error"


transitions: abc.Sequence[TransitionDict] = (
    TransitionDict(
        trigger="wake_up",
        source="asleep",
        dest="hanging_out",
    ),
    TransitionDict(trigger="hunt", source="hanging_out", dest="hunting"),
    TransitionDict(trigger="eat", source="hunting", dest="eating"),
    TransitionDict(
        trigger="hang_out",
        source=["hunting", "eating"],
        dest="hanging_out",
    ),
    TransitionDict(trigger="sleep", source="hanging_out", dest="asleep"),
    TransitionDict(trigger="error", source="*", dest="error"),
)


@attr.s(auto_detect=True)
class PenguinContext:
    hunts: int = 0
    fish_consumed: int = 0


@attr.s(auto_detect=True)
class Penguin(Model):
    """
    instance is callable that receives an `eventtype`.

        >>> penguin = Penguin.new()
        >>> penguin.state
        <States.asleep: 'asleep'>
    """

    ctx: PenguinContext = attr.ib(default=attr.Factory(PenguinContext))

    @classmethod
    def new(
        cls,
        transitions: abc.Sequence[TransitionDict] = transitions,
        states: type[Enum] = States,
        initial: Enum = States.asleep,
    ) -> "Penguin":
        """
        Create a new penguin object.

        returns
        -------
        Penguin
        """
        return super().new(transitions=transitions, states=states, initial=initial)

    def on_enter_eating(self, event_data: EventData) -> None:
        """
        Increment the count of eaten fish then return to "hanging out".

            >>> penguin = Penguin.new()
            >>> penguin.ctx.fish_consumed
            0
            >>> penguin.to_eating()
            True
            >>> penguin.ctx.fish_consumed
            1
            >>> penguin.state
            <States.hanging_out: 'hanging_out'>

        Parameters
        ----------
        event_data : EventData
        """
        self.ctx.fish_consumed += 1
        self.hang_out()

    def on_enter_hunting(self, event_data: EventData) -> None:
        """
        Increment the count of hunts, then either eat any fish caught, or return to
        hanging out.

            >>> penguin = Penguin.new()
            >>> penguin.ctx.hunts
            0
            >>> penguin.to_hunting()
            True
            >>> penguin.ctx.hunts
            1
            >>> penguin.state
            <States.hanging_out: 'hanging_out'>

        Parameters
        ----------
        event_data : EventData
        """
        self.ctx.hunts += 1
        trigger = random.choice(["eat", "hang_out"])
        self.trigger(trigger)

    def __call__(self, event: EventType) -> None:
        """
        Call the Penguin with an event to have it do something.

            >>> penguin = Penguin.new()
            >>> penguin.state
            <States.asleep: 'asleep'>
            >>> penguin(EventType(event=("penguin", "wake_up"), ctx={}))
            >>> penguin.state
            <States.hanging_out: 'hanging_out'>
            >>> penguin(EventType(event=("penguin", "hunt"), ctx={}))
            >>> penguin.ctx.hunts
            1
            >>> try:
            ...    penguin(EventType(event=("fish", "sleep"), ctx={}))
            ... except ValueError as e:
            ...    print(e)
            penguin received 'fish' event.

        Parameters
        ----------
        event : EventType
        """
        if event.event[0] != "penguin":
            raise ValueError(f"penguin received '{event.event[0]}' event.")
        self.trigger(event.event[1], event=event)
