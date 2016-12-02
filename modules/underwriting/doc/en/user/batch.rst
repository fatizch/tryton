Underwriting activation batch [underwriting.activate]
=====================================================

This batch activates the underwritings which are in a draft state, with at
least one decision with an effective date smaller then the treatment date.

The activation will render all provisional decisions effective after the
associated date. It will also trigger document requests creations depending on
the underwriting type configuration.

*Suggested frequency: daily*
