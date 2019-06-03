Batch de résiliation automatique des garanties [``contract.option.terminate``]
==============================================================================

Ce batch résilie les garanties dont la date de fin automatique est dépassée et
dont le paramétrage sur la garantie définit le comportement de résiliation
automatique ainsi que le sous-statut approprié.
- date de fin automatique de la garantie doit être postérieure ou égale à la
  date de traitement du batch.

En conséquence, le statut de ces garanties passera à "résilié" et le
sous-statut défini sur le paramétrage de cette dernière lui sera
appliqué.

*Fréquence suggérée: quotidienne*

Batch de résiliation pour fin de contrat [``contract.termination.process``]
===========================================================================

Ce batch clôt les contrats qui valident les conditions suivantes :
- status actif ou suspendu
- date de fin de contrat non renseignée (``None``) ou non postérieure à la date de traitement

En conséquence, le statut de ces contrats est passé à "résilié".
En fonction du contrat, des actions supplémentaires liées à la clôture peuvent être exécutées (émission de courriers, etc.).

*Fréquence suggérée: quotidienne*
