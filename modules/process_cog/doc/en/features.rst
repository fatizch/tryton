- **Simple Process**: Allows to create a basic process, with only a step list.
  All transitions are allowed between all steps, the default execution order is
  the that of the step list.

- **Per Product Process**: It is possible to configure different process for
  the same action depending on other parameters (typically, insurance product)

- **Easy navigation**: A process can be configured to have *Previous* and
  *Next* buttons on all steps, which helps navigating linear processes.

- **Light controls**: Using a step-defined domain, it is possible to block
  leaving the step (through the client) unless special conditions are met. This
  allows to define simple constraints through pure configuration

- **Event triggered process**: Events can be configured to start processes.
  They can be linked to either the original object which triggered the event,
  or one related to it (provided the link is properly defined). It is also
  possible to chose the step at which the process will start.
