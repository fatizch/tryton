- **Batch de création et de traitement des paiements**

- **Ajout des informations de paiement sur la synthèse acteur**

- **Gestion automatisée des rejets de paiement**

    - Paramétrage des raisons d'un rejet
    - Paramétrage par raisons des actions à exécuter suite à un rejet
    - Paramétrage de la lettre de notification de rejet selon la raison de rejet

- **Blocage des reversements d'un acteur**
    Il est possible de bloquer depuis un acteur tous les versements qu'on aurait
    été amené à lui faire. La dette est bien comptabilisée (montant négatif sur
    le compte à payer) mais tant que le blocage existe aucun paiement ne peut
    être généré. Utile si l'acteur est en virement automatique et que l'on
    souhaite suspendre temporairement ses reversements.
