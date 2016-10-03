- **Data export / import:** This feature aims to help with data transfers
  between distinct databases. Typical use case: transfer configuration between
  testing and production database. It is also used as a base toolset to
  exchange data through web services with other systems.

- **Grouped exports:** In order to create consistent exports, it is possible to
  define data groups to be exported, and to save them for future reuse.

- **Test Cases encapsulation:** This module adds tools to easily create and
  manage test cases to be run on empty databases to quickly bootstrap a new
  installation (accounting configuration, banks, etc...).
  This feature allows test case hierarchisation, and previously run test cases
  detection.

- **Unittest helpers:** Unittest tooling, used to define unittest dependencies
  and transactional rollback of unittests. This allows to avoid copy pasting
  testing code, and avoid breaking tests down the line by creating or deleting
  new entries in the database.

- **Functional Errors:** If there are N functional errors that should be
  triggered on an action, it is usually better to display all errors at once to
  the user, so he can fix all at once before trying again. Functional errors
  allow to do that with the error_manager context manager.

- **Tags:** Allows to *tag* models, especially useful in the configuration part
  of the application to easily filter on any kind of models.

- **Event:** Toolset for handling functional events notifications. This allows
  to define and trigger actions when required. Possible actions can be enriched
  in modules, and may be a simple log storage to external services calls. Any
  action can be filtered on using Pyson expressions to be more accurate
  regarding what is triggered.

- **Batch framework:** Add a batch framework to define a unified model to write
  and handle batchs. This structure handles return codes, multiprocess handling
  (using celery) and failover.

- **Handle past / future connexion simulation:** Allows for testing purpose
  mainly to connect with *today* set in the past or future. Allows to simulate
  future actions, or check past status.

- **Date manipulation:** Dev tools to manipulate dates. basically wrappers for
  *dateutils* functions, interval calculations, etc...

- **String manipulation:** Dev tools to handle strings. Formatting, asciify,
  slugify, etc...

- **Tryton tools:** Evaluate domains, pyson, filter versioned lists, etc...

- **User defined historization:** Allow the user to manually define that a
  model should be historized through the *Model* entry point in the
  application. The required module update will not be triggered, and
  deactivating a previously historized model will not remove the history table
  in the database. Also, models which are "hardcoded" as historized will not be
  modifiable.
