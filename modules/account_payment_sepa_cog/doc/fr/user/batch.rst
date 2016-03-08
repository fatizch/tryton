Batch de traitement des rejets [account.payment.fail]
=======================================================

Ce batch créé un message SEPA, y associe le message de rejet et traite les paiements
pour chaque fichier dans le répértoire spécifié en entrée.

- *Fréquence suggérée:* quotidienne
- *in*: Argument spécifiant le dossier d'entrée comportant les fichiers de rejet.
- *out*: Argument spécifiant le dossier de sortie qui comportera les fichiers de rejet
  traités.

**Les deux arguments in et out sont necessaires au batch pour fonctionner**
