Batch de création de paiements [account.payment.create]
=======================================================

Ce batch créé des paiements et groupes de paiements pour les lignes de
mouvements qui valident les critères suivants :

- mandat SEPA valide de configuré
- date de paiement antérieure à la date de traitement
- aucun paiement non échoué associé
- aucun mouvement de réconciliation associé

Les paiements sont créés avec le statut "Approuvé".

- *Fréquence suggérée:* quotidienne
- *Date de traitement à fournir:* prochaine date de prélèvement postérieure à
  la date du jour
- *Méthodes de traitement à fournir*: Méthode de traitement des journaux pour
  les paiements à traiter, séparés par des virgules.
  exemple: sepa,manual
  Afin de traiter les paiement SEPA et chèques.


Batch de traitement de paiements [account.payment.process]
==========================================================

Ce batch fait passer les paiements du statut "Approuvé au statut
*Traitement* et génère le fichier de prélèvements SEPA à transmettre à la
banque.

- *Fréquence suggérée:* X jours avant chaque date de prélèvement possibles
  sur les contrats

Ce batch possède les paramétrages suivants à définir dans une section
``account.payment.process`` du fichier de configuration batch.


Batch de validation des paiements [account.payment.acknowledge]
===============================================================

Ce batch passe le statut des paiements de l'état 'Traité' à l'état 'Validé'.

Les paramètres suivants sont disponibles:

- *group_reference'*: permet de spécifier l'identifiant précis d'un groupe de
  paiement.
- *kind* (receivable ou payable) : définit quel type de paiements seront
  validés. Tous les paiement de ce type à l'état traitement seront validés.
- *Méthodes de traitement à fournir*: Méthode de traitement des journaux pour
  les paiements à traiter, séparés par des virgules.
  exemple: sepa,manual
  Afin de traiter les paiement SEPA et chèques.

Si les deux paramètres sont spécifiés, seul group_reference sera utilisé.
