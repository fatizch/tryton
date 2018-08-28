Module event_log
================

The event_log module allows to record informations about actions made in coog.

For example, when this module is installed, every contract activation
leads to the creation of an event log, with a link to the contract,
the kind of event (contract activation), the name of the user who made the
action, and the precise date at which the event occured.

It is also possible to configure the creation of event logs with tryton
triggers. For an event_log to be created that way, one needs to create a
tryton trigger, and to designate Event Log as the action model in said trigger.
One also needs to designate the function "create_event_logs" as the "action
function" of the trigger.
