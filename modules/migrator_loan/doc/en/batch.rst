Batches list and recommended execution order.
Execution times are just indicative and depend of server/database/network/etc
configurations.

`migrator.loan.increment` is called by `migrator.loan`, and thus doesn't need
to be executed via the command line interface.

# migrator.lender

- updatable: non
- concurrency: n

# migrator.loan

- updatable: non
- concurrency: n
- execution time: 1' / 30 records

# migrator.loan.increment

- updatable: non
- concurrency: n
