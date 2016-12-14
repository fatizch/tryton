Les temps d'exécution sont là uniquement pour donner un ordre d'idée et
dépendent évidemment des configuration des serveurs/base de données/réseau,
etc.

# migrator.payment

Migration des paiements.
Ce batch recquiert d'avoir paramétré dans `batch.conf` les *account_code* et
*journal_code* qui sont utilisés pour la création des mouvements et lignes
associées.

- updatable: non
- concurrency: n
- temps d'exécution: 1' / 10000 enregistrements

