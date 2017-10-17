Batch de rejet des devis inactifs [``contract.decline.inactive_quotes``]
========================================================================

Ce batch décline les contrats qui valident les conditions suivantes :
- status devis (quote).
- La dernière date de modification du devis dépasse le delai maximum définit dans la configuration "Administration produit".

En conséquence, le statut de ces contrats est passé à "Décliné".
Le sous-status (raison) est assigné en fonction du champs "Raison de la déclinaison automatique" dans la configuration "Administration produit".

*Fréquence suggérée: quotidienne*
