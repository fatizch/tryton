Batches list and recommended execution order.
Execution times are just indicative and depend of server/database/network/etc
configurations.

# migrator.payment

This batch requires to define *account_code* and *journal_code* settings in
`batch.conf` for the creation of accpunt moves and corresponding move lines.

- updatable: non
- concurrency: n
- execution time: 1' / 10000 records

