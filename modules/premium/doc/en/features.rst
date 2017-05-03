- **Configuration of fees:** Possibility to define fees in the application.
  These fees are attached to products (and eventually other entities).

- **Configuration of tarification rules:** Product / guarantees can have
  a list of tarification rules. The rules constitute:

  - A calculation rule

  - The frequency of calculations. This frequency indicates which unit is 
    returned by the rule. For example, if the rule returns "10" and that the
    frequency is "Yearly", the resulting rate is "10 euro yearly".

  - The basis of pricing. In this module the possible levels are "Contract"
    and "Option". The rule will be calculated for each corresponding element
    on the contract with an on-going rate.

  It is important to note that there can be multiple rules, who will all
  be evaluated depending on the context.

- **Configuration of taxes:** Next to the tarification rules, it is possible
  to specify the taxes which apply to the result of calculations of these
  rules.

- **Premium date configuration :** List of dates for premium calculation. 
  The contract start date is used by default but other dates could be added :
    + annually at the contract anniversary
    + annually at a custom date (January 1st for example)
    + with a relative duration from the contract start date 
      (1 month after the contract start date for a free month for example)

- **Calculation of premiums on a contract:** Recalculating the contract triggers
  a recalculation of premiums on a contract. These premiums are the output
  of the tarification rules, and are used in the module ``contract_insurance_invoice``
  to generate the invoices of a contract.

- **Preview premiums:** It is possible from a contract to preview the premiums
  calculated if the contract is active.
