- **Unitary amendment for modifying invoicing data :** Allow modification, on a
  contract, the invoicing options. These modifications can be planned for the 
  future, and modify the frequency, the payment mode, the user account, etc ...

- **Concept of endorsement rates :** It is possible to mark an endorsements as
  *rates*. This signifies that:

  - The application of the endorsment will trigger the recalculation of
    rates on the contracts starting from the effective date.

  - This recalculation will be following by the deletion / cancellation of
    invoices prior to the endorsment, depending on their status (invoices in
    draft or valid invoices will be deleted, issued or paid invoices will
    be cancelled, and accounting will be updated).

  - The invoices will then be recreated / emitted to take in account the new
    rates.

  - These features will be replicated in the case of a cancelled
    endorsement.

It is important to note that these rate endorsements force the generation of an
invoice starting at their effective date.
