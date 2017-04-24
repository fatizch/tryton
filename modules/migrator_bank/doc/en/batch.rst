Batches list and recommended execution order.
Execution times are just indicative and depend of server/database/network/etc
configurations.

# migrator.bank

- updatable: yes
- concurrency: n
- execution time: 1' / 1000 records

# migrator.bank_agency

- updatable: no
- concurrency: n
- execution time: 1' / 10000 records

# migrator.bank_account

To enable parallel processing, this batch exposes a *create* flag corresponding
 to two execution modes :
- ``coog batch generate migrator.bank_account --create 1``: create bank
  accounts, create sepa mandate of first owner extracted from source database
  for each account
- ``coog batch generate migrator.bank_account --create 0``: add owners to bank
  accounts, create sepa mandates for those parties

- updatable: non
- concurrency: n
- execution time: 1' / 10000 records
