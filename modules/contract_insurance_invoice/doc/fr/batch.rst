Batch de création des quittances [contract.invoice.create]
==========================================================

Pour tous les contrats au statut "actif", crée les quittances dont la date de
fin est strictement inférieure à la date de traitement et leur donne le statut
"validé".

*Fréquence suggérée:* quotidienne*
*Date de traitement à fournir:* date du jour

Batch d'émission des quittances [contract.invoice.post]
=======================================================

Fait passer toutes les quittances validées dont la date de début est
inférieure ou égale à la date de traitement au statut "émises".

*Fréquence suggérée: quotidienne*
*Date de traitement à fournir:* date du jour
