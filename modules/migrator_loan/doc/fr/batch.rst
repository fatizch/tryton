Les temps d'exécution sont là uniquement pour donner un ordre d'idée et
dépendent évidemment des configuration des serveurs/base de données/réseau,
etc.

`migrator.loan.increment` étant appelé par `migrator.loan`, il n'a
pas à être exécuté via la ligne de commande.

# migrator.lender

Migration des organismes prêteurs

- updatable: non
- concurrency: n

# migrator.loan

Migration des prêts.

- updatable: non
- concurrency: n
- temps d'exécution: 1' / 2000 enregistrements

# migrator.loan.increment

Migration des paliers de prêt.

- updatable: non
- concurrency: n
