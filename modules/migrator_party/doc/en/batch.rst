Batches list and recommended execution order.
Execution times are just indicative and depend of server/database/network/etc
configurations.

# migrator.country

- updatable: yes
- concurrency: n
- execution time: 1'

# migrator.zip

When a row has a zipcode not in coog, the city field must be present for the
zip code to be created.

- updatable: no
- concurrency: n
- execution time: 1' / 10000 records

# migrator.party

- updatable: yes
- concurrency: n
- execution time: 1' / 10000 records

# migrator.party.relation

- updatable: no
- concurrency: n
- temps d'exécution: 1'

# migrator.contact

- updatable: no
- concurrency: n
- execution time: 1'

# migrator.address

- updatable: no
- concurrency: n
- execution time: 1'
