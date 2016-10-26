Batch de résiliation pour fin de contrat [contract.termination.process]
=======================================================================

Ce batch clôt les contrats qui valident les conditions suivantes :
- status actif ou suspendu
- date de fin de contrat non renseignée (``None``) ou non postérieure à la date de traitement

En conséquence, le statut de ces contrats est passé à "résilié".
En fonction du contrat, des actions supplémentaires liées à la clôture peuvent être exécutées (émission de courriers, etc.).

*Fréquence suggérée: quotidienne*

Batch de rejet des devis inactifs [contract.decline.inactive_quotes]
====================================================================

Ce batch décline les contrats qui valident les conditions suivantes :
- status devis (quote).
- La dernière date de modification du devis dépasse le delai maximum définit dans la configuration "Administration produit".

En conséquence, le statut de ces contrats est passé à "Décliné".
Le sous-status (raison) est assigné en fonction du champs "Raison de la déclinaison automatique" dans la configuration "Administration produit".

*Fréquence suggérée: quotidienne*
