python-state-machine
===

Python & docker template State Machine application using Transitions, Attrs, Cattrs and 
Structlog.

This example application creates two state machines. The first is an event dispatcher
that is callable with a specific event type, and the second an event handler to handle
any `penguin` events that are dispatched.

The base `Model` class demonstrates a pattern for logging the state of the instance 
at each transition between states.

### Usage Example

```python-repl
>>> from app.event_dispatcher import Dispatcher, EventType
>>> from app.penguin_handler import Penguin
>>> penguin = Penguin.new()
>>> penguin.state
<States.asleep: 'asleep'>
>>> Dispatcher.register_handler(("penguin",), penguin)
>>> dispatcher = Dispatcher.new()
>>> dispatcher.state
<States.invoked: 'invoked'>
>>> dispatcher(EventType.new("penguin:wake_up", ctx={}))
>>> dispatcher.state
<States.handled: 'handled'>
>>> penguin.state
<States.hanging_out: 'hanging_out'>
>>> new_dispatcher = Dispatcher.new()
>>> new_dispatcher(EventType.new("fish:sleep_with_one_eye_open", ctx={}))
>>> new_dispatcher.state
<States.dropped: 'dropped'>

```

We instantiated an instance of penguin and assigned it as a handler to any event that 
starts with the `penguin` prefix. We then instantiated an instance of the dispatcher and
dispatched a `penguin:wake_up` event through the dispatch model, which is eventually 
handled by the `Penguin` instance.

The example demonstrates the shift through states that occurs for each of the 
`dispatcher` and the `penguin` as the event is dispatched and handled.

### Development

New model instances must be instantiated via their `Model.new()` constructor. This
method instantiates the `attrs` model, and configures the instance as a state machine.
The `new()` classmethod is where the states and transitions of the machine are 
configured. For example the default `Model.new()` method returns an instance that is
instantiated with `States` states, `States.invoked` as the initial state, and a single
transition from `*` (any state) to `States.error`. Real world implementations of this
pattern should set the states and transitions to whatever makes sense for the use-case.
  
```python
@classmethod
def new(
    cls: type[ModelType],
    transitions: abc.Sequence[TransitionDict] = (
            TransitionDict(trigger="error", source="*", dest="error"),
    ),
    states: type[Enum] = States,
    initial: Enum = States.invoked,
) -> ModelType:
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
```

```python-repl
>>> from app.model import Model
>>> my_instance = Model.new()

```

Machines have states, and are always in a state. New machines that haven't done 
anything yet will be in the "invoked" state. By default, the `Model` type only knows
about two states: "invoked" and "error".

```python-repl
>>> my_instance.state
<States.invoked: 'invoked'>

```

Transitions move the model from one state to another. The base `Model` class has a 
single transition defined that allows the machine to move from any existing state to
the "error" state via the `error()` trigger method.

```python-repl
>>> my_instance.error()
True
>>> my_instance.state
<States.error: 'error'>

```

To have our model do anything useful, we'll add some extra states and transitions.

```python-repl
>>> from enum import Enum
>>> import attr
>>> class DispatchStates(str, Enum):
...     dispatching = "dispatching"
...     handled = "handled"
...     dropped = "dropped"
... 
>>> dispatch_transitions = [
... {"trigger": "dispatch_event", "source": "invoked", "dest": "dispatching"},
... {"trigger": "handle", "source": "dispatching", "dest": "handled"},
... {"trigger": "drop", "source": "dispatching", "dest": "dropped"},
... {"trigger": "error", "source": "*", "dest": "error"},
... ]
>>> @attr.s(auto_detect=True)
... class Dispatcher(Model):
...     ctx: dict = attr.ib(factory=dict)
...     @classmethod
...     def new(cls, *args, **kwargs):
...         inst = super().new(*args, **kwargs)
...         inst.add_states(DispatchStates)
...         inst.add_transitions(dispatch_transitions)
...         return inst

```

Every `Model` subclass needs to define a transition away from the "invoked" state, 
such as the "dispatch_event" trigger above.

Also notice the final transition added above, the "error" trigger. This is the same
trigger that we've already seen exists on the `Model` class. We add it again as without
this the error state would not be accessible from any of our `DispatchStates` which we
need as `Model` will automatically try to put the model into "error" state if an 
unhandled exception occurs during any state transition.

Now we can do something more meaningful:

```python-repl
>>> dispatcher = Dispatcher.new()
>>> dispatcher.state
<States.invoked: 'invoked'>
>>> dispatcher.dispatch_event("some event")
True
>>> dispatcher.state 
<DispatchStates.dispatching: 'dispatching'>
>>> dispatcher.handle()
True
>>> dispatcher.state 
<DispatchStates.handled: 'handled'>

```

It doesn't make sense for the dispatcher model to move from "handled" to "dropped" and
the model will not allow it (because we haven't defined a transition between those 
states):

```python-repl
>>> try:
...    dispatcher.drop()
... except Exception as e:
...    print(e)
"Can't trigger event drop from state handled!"

```

Still, this example isn't very useful. We need to be able to perform some actions on
the back of the state changes and `transitions` performs a bit of magic to make this
possible. When we add states and transitions to the model, we get the ability to define
callbacks that are invoked in different phases of the model's lifecycle.

Transitions have "before", "after" and "prepare" callbacks (see 
[here](https://github.com/pytransitions/transitions#transition-callbacks)) for more info.

States have "enter" and "exit" callbacks, and we can define `on_enter_<<state name>>()` 
and `on_exit_<<state_name>>()` methods on our model.

We can use these callbacks to perform operations that make the instance consistent with
the state that it is entering/has entered/is exiting, etc.

### Transitions Library

An outline of the main `Transitions` types and interesting attributes (not all object attributes are
listed here).

- `Machine` -  Manage states, transitions and models. In case it is initialized without a specific model
    (or specifically no model), it will also act as a model itself. Machine takes also care of decorating
    models with conveniences functions related to added transitions and states during runtime.
  - `states`: ordered dict of registered states
  - `events`: ordered dict of transitions ordered by trigger/event
  - `models`: list of models 
  - `initial`: name of initial state for new models
  - `prepare_event`: list of callbacks executed when event is triggered
  - `before_stage_change`: list of callbacks executed after condition checks but before transition
  - `after_stage_change`: list of callbacks executed after the transition
  - `finalise_event`: list of callbacks executed after all transitions callbacks executed
- `MachineError` - Used for issues related to state transitions and current states.
    For instance, it is raised for invalid transitions or machine configuration issues.
- `Event` - A collection of transitions assigned to the same trigger.
  - name: name of the event, which is also the name of the triggering callable (e.g., 'advance' implies an advance() method).
  - machine: the current `Machine` instance
- `EventData` - Collection of relevant data related to the ongoing transition attempt.
  - state: the State from which the Event was triggered
  - event: the triggering Event
  - machine: the current machine instance
  - model: the model/object the machine is bound to
  - args: positional arguments from trigger method
  - kwargs: keyword arguments from trigger method
  - transition: active transition, assigned during triggering
  - error: assigned here if triggered event causes an error
  - result: if transition successful - bool
- `Transition` - representation of a transition managed by a `Machine`
  - `source`: source state of the transition
  - `dest`: destination state of the transition
  - `prepare`: list of callbacks executed before conditions checks
  - `conditions`: list of callbacks to determine if the transition should be executed
  - `before`: list of callbacks executed before transition execute if all conditions pass
  - `after`:list of callbacks executed after transitions execute if all conditions pass
- `State` - a persistent representation of a state managed by a `Machine`.
  - `name`: string name which is also assigned to the model
  - `on_enter`: list of callbacks executed when state is entered
  - `on_exit`: list of callbacks executed when state is exited
  
### Requirements

* Docker

#### Setup

Copy `.env.example` to `.env`

#### Run
`$ docker-compose up --build`

#### Run Tests
`$ docker-compose run --rm app scripts/tests`
