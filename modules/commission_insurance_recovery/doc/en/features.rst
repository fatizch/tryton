- **Configuration of recovery amount**: The amount to be taken back after
  termination of a contract is configurable using the rule engine at the level
  of a commisionnent. For example, it is possible to configure a recovery of 10%
  increase in commissions paid if the contract is terminated during the first year
  and 5% if it is terminated during the second year.

- **Generation of commissions**: during a termination of a contract, commissions
  with a type 'recovery' are generated in function of the recovery amount configured.
  When the contract is reactivated, these commissions are cancelled or deleted if
  they are not yet paid.
