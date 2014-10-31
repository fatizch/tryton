Module Endorsement Full Contract Revision
=========================================

This modules add the possibility to start a full contract revision using the
endorsement process. This particular process uses the ``in-progress``
endorsement state to place the contract in an unstable (``quote``) state, so
that it can be freely modified.

Modification is possible through the use of a new process kind. Upon starting
the endorsement, the user will trigger the start of a process matching this
kind. The button ``revert_current_endorsement`` should be available anytime
during this process (for instance by setting it in the process' ``xml_footer``
field). This button, once clicked, will reset the contract in the exact state
it was before starting the endorsement.

The process shoud also implement the ``apply_in_progress_endorsement`` method
pluged in to be executed upon completion, in order to effectively complete the
endorsement.

Note that as it is the case for all endorsements which uses the ``in-progress``
state, other endorsements will be impossible to apply while the endorsement is
neither completed nor aborted.
