Liste des batches dans l'ordre recommandé d'exécution.
Les temps d'exécution sont là uniquement pour donner un ordre d'idée et
dépendent évidemment des configuration des serveurs/base de données/réseau,
etc.

# Batches à lancer via `coog batch`

## migrator.contract

Migration des contrats.
Ce batch dispose d'un flag --skip_extra_migrators qui permet notamment de
spécifier si on souhaite migrer les premiums (par défaut) ou les calculer
(``--skip_extra_migrators migrator.contract.premium``).

- updatable: non
- concurrency: n
- temps d'exécution: 1' / 600 enregistrements (comprend temps d'exécution des extra migrators)

## migrator.contract.version

Migration des données d'avenant.

- updatable: non
- concurrency: 1
- temps d'exécution: 1' / 10000 enregistrements

## migrator.contract.premium_waiver

Migration des exonérations

- updatable: non
- concurrency: n
- temps d'exécution: 1' / 10000 enregistrements


# Batches lancés par migrator.contract en tant que extra migrators

# migrator.contract.option

Migration des garanties.

# migrator.contract.event

Migration des évènements

# migrator.contract.premium

Migration des primes
