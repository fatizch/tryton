- **Event-triggered emails**: Configure emails to be sent when certain events
  are happening in the application. It is possible to configure the sender,
  recipients, subject and body of the email.

- **Context base body**: A simple syntax can be used in the body to access the
  fields of the object that triggered the event to customize the email
  contents.

- **Isolation... or not**: The email can be configured as "blocking" or
  "non-blocking". Depending on this configuration, the errors which may happen
  when sending the email will abort the original action or not.
