- **Covered element :** Complete the contract's modelization with the covered
  element notion. A covered element is the entity or entities insured by the
  contract. It can be a person, a habitation, a car, etc... Covered elements
  are directly attached to a contract et subscribe to options independently
  of each other, with eventually different parameters.
  Covered elements are modified according to the risks descriptions associated
  to the product (cd **offered_insurance**)

- **Extra premiums :** Extra premiums are a generic term to represent pricing
  changes. These changes can be increases or decreases.

- **Renewal :** Insurance contracts are frequently renewed at maturity date.
  This module contains tools allowing to handle renewals.

- **Exclusions management :** The contract takes into account the exclusions
  defined in the options settings in order to limit subscription possibilities.

- **Extra data :** Subscribed options can enquire extra data defined in the
  associated offered options through the ``offered_insurance`` module.
