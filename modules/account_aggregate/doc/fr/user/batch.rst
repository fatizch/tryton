Batch de création de snapshot des mouvements comptables [``account.move.snapshot.take``]
========================================================================================

Crée un snapshot sur les mouvements comptables au statut "émis" et qui ne
figurent pas déjà dans une précédente snapshot.
Tous les mouvements sélectionnés se voient attribuer le même numéro d'
"instantané".
Le snapshot est utilisé par le batch *account.move.snapshot.export*

- *Fréquence suggérée:* quotidienne
- *Date de traitement à fournir:* **ignorée**. Le batch considère les
  mouvements qui sont "émis" à la date d'exécution.
