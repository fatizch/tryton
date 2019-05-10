- **Business APIs**: Business APIs are designed to offer a stable interface,
  meaning it does not depend on the underlying data structure (this is the
  opposite of what the usual low-level Tryton APIs does). The main objective is
  to provide a framework for designing and writing APIs which includes from the
  start the handling of the modularity problem
- **Access Rights**: Business APIs shall have separate, dedicated access right
  management. They will always be executed with unlimited access rights, so
  knowing and managing who is allowed to access them is a must
- **Structured errors**: Since those APIs are designed for communication with
  other systems, these APIs must return something more manageable than a simple
  string in case of an error. The use of this framework allows to centralize
  error management, and proposes a way to transform text errors into structured
  data
- **Input / Output validation**: In order to offer resilient APIs, it is a must
  to offer input / output data validation. To do so, business APIs natively
  include JSON Schema management. Input data must validate against one such
  schema (defined by the developpers), while output data are only checked in a
  development environment (to avoid an overhead in production)
- **Auto description**: Each business API comes with a dedicated sister API
  which describes it, so that any system / developper can know its behaviour
  (most importantly, its input / output schema)
