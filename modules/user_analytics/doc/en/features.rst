- **User connection structure**: User connection are linked with the user, and
  with the current session. It creates a user connection per day and per
  session.

- **Session activity**: Every user actions will logs some activity. If the user
  inactivity reach the inactiviy configuration limit, then it will logs
  inactivity.
  The activity/inactivity loogin remains even if the user logs out or after a
  cnnection timeout.
