- **Step creation**: A business process is basically a list of steps. We allow
  to manually create those steps from the application, and combine them to
  create the best process for the situation. A given step can be used across
  multiple processes.

- **View design**: The step configuration allows to design specific views for
  each step, so the final process has the finest control on what the end user
  will see. It is also possible to add a header and / or a footer on the whole
  process.

- **Soft controls**: On each step, we can easily add controls from the
  configuration interface. Those control may be simple (a given field is
  required) or more complex, in which case they will use methods available from
  the application code base.

- **User right managements**: A given step can be configured to be only
  accessible to certain users (underwriting, validation, etc...)

- **Control flow**: All transitions between steps can be finely controlled. As
  a default rule, everything is possible, the user can jump around in the
  process, and will only be stopped if a specific check fails. The other way is
  possible as well, where only the transitions that are specifically allowed
  are available.

- **Safe save**: A running proces can be suspended and resumed at any time.
  Multiple processes can be handled at the same time by a given user.
