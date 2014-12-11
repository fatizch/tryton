Batch de création des quittances [contract.invoice.create]
==========================================================

Ce batch doit tourner quotidiennement pour clore les contrats actifs ou suspendus.

Sur chaque contrat dont la date de fin est inférieure ou égale à la date du jour, il appelle la méthode terminate, qui doit au minimum passer le statut du contrat à "terminated" (résilié). En fonction du contrat, d'autres comportements sont possibles (émission de courriers, etc.).


Batch d'émission des quittances [contract.invoice.post]
=======================================================

TODO
