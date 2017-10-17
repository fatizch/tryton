Liste des batches dans l'ordre recommandé d'exécution.
Les temps d'exécution sont là uniquement pour donner un ordre d'idée et
dépendent évidemment des configuration des serveurs/base de données/réseau,
etc.

# migrator.bank

Migration des banques

- updatable: oui
- concurrency: n
- temps d'exécution: 1' / 1000 enregistrements

# migrator.bank_agency

Migration des agences bancaires

- updatable: non
- concurrency: n
- temps d'exécution: 1' / 10000 enregistrements

# migrator.bank_account

Migration des comptes bancaires et mandats sepa.
Afin de permettre la parallélisation des traitements, ce batch dispose d'un
flag *create* et doit être exécuté à deux reprises :

- ``coog batch generate migrator.bank_account --create 1``: crée les comptes
  bancaires, créé le mandat du premier titulaire extrait de la base pour
  chaque compte

- ``coog batch generate migrator.bank_account --create 0``: ajoute des
  titulaires aux comptes bancaires, créé les mandats de ces tiers

- updatable: non
- concurrency: n
- temps d'exécution: 1' / 10000 enregistrements
