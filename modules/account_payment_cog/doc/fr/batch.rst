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

Batch de traitement de paiements [account.payment.process]
==========================================================

Ce batch fait passer les paiements du statut "Approuvé au statut
*Traitement* en générant optionnellement au passage le fichier de
prélèvements SEPA à transmettre à la banque (cf :ref:`dump_sepa_xml`).

- *Fréquence suggérée:* autant de fois que de dates de prélèvement possibles 
  sur les contrats

Ce batch possède les paramétrages suivants à définir dans une section
``account.payment.process`` du fichier de configuration batch.

.. _dump_sepa_xml:

dump_sepa_xml
~~~~~~~~~~~~~

Booléen indiquant si le batch doit exporter les fichiers sepa de chaque groupe
de paiement au format xml.
Défaut : ``no``


