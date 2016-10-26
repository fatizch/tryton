Batch de création des bordereaux de commissions [commission.invoice.create]
===========================================================================

Pour tous les courtiers ou les assureurs qui ont des commissions payables avant
la date de traitement, un bordereau sera généré avec un statut brouillon.

- *Fréquence suggérée:* mensuel
- *Date de traitement à fournir:* date de la fin du mois précédent
- *agent_type:* cette option est obligatoire pour générer des bordereaux. Deux
  options sont possibles

    - 'agent': seul les bordereaux courtiers seront générés
    - 'principal': seul les bordereaux assureurs seront générés

Batch d'émission des bordereaux de commissions [commission.invoice.post]
========================================================================

Fait passer tous les bordereaux validés au statut "émis" et créé les lignes de
mouvements correspondantes.

- *Fréquence suggérée:* mensuel
- *Date de traitement à fournir:* non nécessaire
- *agent_type:* cette option est obligatoire pour émettre des bordereaux. Deux
  options sont possibles

    - 'agent': seul les bordereaux courtiers seront émis
    - 'principal': seul les bordereaux assureurs seront émis

Ce batch ne supporte pas l'exécution en multi process.
