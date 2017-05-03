- **Document Request**: Create and mangage document requests. The request is
  linked to an object that needs it (a contract, claim, ...) and to a document
  type. We store when the document was requested, when it is due, whether it
  is blocking or not, and a link to the received document if available

- **Reception Wizard**: On a document reception, the wizard will try to look
  for a document request matching the received document, then automatically
  attach both together

- **EDI interface**: Document requests can be linked to actual documents in the
  EDI. This allows to quickly consult a document from the "main object"
  (contract, etc...) view

- **Request batch**: A batch is available to automatically send a document
  request letter for overdue requested documents
