- **Commission plans**

    - The *commission method* allows defining when commissions are due when
      *posting* or *paying* the invoice
    - The plan *type* allows to make the difference between the insurer's
      commission plan and the broker's commission plan.
    - The *insurer plan* allows to associate a broker's commission plan to an
      insurer's commission plan
    - *Lines* allow defining the commission formula to apply for a set of
      options (which can be attached to different products)
    - *Computation dates* allow specifying at which dates the commission rate is
      likely to change for the different lines.

- The **commission agent** is the link between an insurer's intermediate (
  an insurer or a broker) and an associated commission plan.
  The agent can have a start date and an end date.

- **The commission agent creation wizard** allows mass entry of all necessary
  information to compute different commissions for a set of brokers
  a set of brokers

- The **Commission invoices generation wizard** allows generating different
  broker invoices

- **Broker fee management**: A fee can be typed as a broker fee. This fee's
  generates a credit in the fee's account. When generating the broker's invoice,
  a line will be generated for all fees of which invoices have been paid.

- **Portfolio's transfer**: An entry point in the application allows transfering
  a portfolio from a broker to another. The transfer may concern all contracts,
  or a set of contracts. It checks agent commissions accounting between the old
  and new broker, and blocks changes in case of incompatibilities.
