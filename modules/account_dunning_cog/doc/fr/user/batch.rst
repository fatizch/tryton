Batch de mise à jour des relances [account.dunning.update]
==========================================================

Ce batch met à jour le niveau des relances existantes en fonction de la date
de traitement.

*Fréquence suggérée: quotidienne*

Batch de generation des relances [account.dunning.create]
=========================================================

Ce batch génère les relances dans un état 'brouillon' pour les lignes
comptables dont la différence entre la date de traitement du batch et la date
de maturité de la ligne a atteint un niveau de relance.

*Fréquence suggérée: quotidienne*


Batch de traitement des relances [account.dunning.treat]
========================================================

Ce batch traite les relances qui sont dans un état brouillon en fonction du
niveau de la relance.

*Fréquence suggérée: quotidienne*
