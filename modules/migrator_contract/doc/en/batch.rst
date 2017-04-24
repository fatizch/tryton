Batches list and recommended execution order.
Execution times are just indicative and depend of server/database/network/etc
configurations.

# Batches to run via `coog batch`

## migrator.contract

This batch has a flag --skip_extra_migrators which allows to specify if one
wants migrate premiums (default) or calculate them (``--skip_extra_migrators
migrator.contract.premium``).

- updatable: no
- concurrency: n
- execution time: 1' / 600 records (include execution time of extra migrators)

## migrator.contract.version

- updatable: no
- concurrency: 1
- execution time: 1' / 10000 records

## migrator.contract.premium_waiver

- updatable: no
- concurrency: n
- temps d'exécution: 1' / 10000 enregistrements


# Batches runned by migrator.contract as extra migrators

# migrator.contract.option

# migrator.contract.event

# migrator.contract.premium
