- **Contract structure**: Service contracts are defined with dates, and options
  (optional services). They are linked to a party, the subscriber, and to a
  product, which represents what is the purpose of the contract

- **Extra data management**: Depending on the selected product, the contract
  may require additional information, which are stored in versioned extra data
  objects

- **Option refusal**: Options on a quote contract may be accepted or declined,
  in which case they will not be considered when analysing the contract details

- **Contract termination**: A contract may be terminated at any time (or only
  at certain dates depending on the product). The termination frees the
  contractors from their obligations after the termination date

- **Void contracts**: Contract may be "voided", in which case everything will
  be as if they never existed in the first place. The typical use case are
  human errors, or legal rules that allows a "reflexion" period during which he
  can cancel his subscription

- **Option subscription**: A wizard is available to subscribe or renounce
  options depending on their configuration. For instance, some will be
  mandatory, others optional, and some may be optional but selected by default
