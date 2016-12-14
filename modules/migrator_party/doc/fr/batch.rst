Liste des batches dans l'ordre recommandé d'exécution.
Les temps d'exécution sont là uniquement pour donner un ordre d'idée et
dépendent évidemment des configuration des serveurs/base de données/réseau,
etc.

# migrator.country

Migration des pays

- updatable: oui
- concurrency: n
- temps d'exécution: 1'

# migrator.zip

Migration des codes postaux. Si on récupère une ligne avec un code postal
non présent dans coog et une ville renseignée, on crée le Zip correspondant.

- updatable: non
- concurrency: 1
- temps d'exécution: 1' / 10000 enregistrements


# migrator.party

Migration des informations d'identité des tiers (personne physique ou morale)

- updatable: oui
- concurrency: n
- temps d'exécution: 1' / 10000 enregistrements

# migrator.party.relation

Migration des relations entre tiers.

- updatable: non
- concurrency: n
- temps d'exécution: 1'

# migrator.contact

Migration des mécanismes de contact

- updatable: non
- concurrency: n
- temps d'exécution: 1'

# migrator.address

Migration des adresses

- updatable: non
- concurrency: n
- temps d'exécution: 1'
