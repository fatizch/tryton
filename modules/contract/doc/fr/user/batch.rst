Batch de résiliation pour fin de contrat [contract.termination.process]
=======================================================================

Ce batch clôt les contrats qui valident les conditions suivantes :
- status actif ou suspendu
- date de fin de contrat non renseignée (``None``) ou non postérieure à la date de traitement

En conséquence, le statut de ces contrats est passé à "résilié".
En fonction du contrat, des actions supplémentaires liées à la clôture peuvent être exécutées (émission de courriers, etc.).

*Fréquence suggérée: quotidienne*
