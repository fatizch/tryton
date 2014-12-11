Batch de création de paiements [account.payment.creation]
=========================================================

Ce batch créé des groupes de paiements pour les quittances qui valident les
critères suivants :

- mandat SEPA valide de configuré
- date de paiement antérieure à la date de traitement
- aucun paiement non échoué associé
- aucun mouvement de réconciliation associé

Ce batch n'a aucune configuration spécifique à l'heure actuelle.

Batch de traitement de paiements [account.payment.treatment]
============================================================

Ce batch fait passer les paiements du statut *Approuvé* au statut
*Traitement* en générant optionnellement au passage le fichier de
prélèvements SEPA à transmettre à la banque (cf :ref:`dump_sepa_xml`).

Ce batch possède les paramétrages suivants à définir dans une section
``account.payment.creation`` du fichier de configuration batch.

.. _dump_sepa_xml:

dump_sepa_xml
~~~~~~~~~~~~~

Booléen indiquant si le batch doit exporter les fichiers sepa de chaque groupe
de paiement au format xml.
Défaut : ``no``


