La mobilité bancaire se traduit par un fichier (nommé flux 5) contenant les informations suffisantes pour la mise à jour des modes de quittancement.

De ce fichier, Coog extrait:
- les identifiants du fichiers et de la demande mobilité bancaire,
- la date de signature du mandat de mobilité bancaire,
- les BICs et IBANs initiaux et mis à jour,
- les RUM des mandats SEPA associés à chaque demande.

Les traitements suivants sont effectués:
- la date de fin du compte bancaire initial est mise à jour,
- les nouveaux comptes bancaires sont créés ou mis à jour. Les propriétaire de ces comptes bancaires sont définis comme étant les signataires des mandats SEPA fournis dans le flux, ou les propriétaires des comptes bancaires initiaux si aucun mandat n'est fourni.
Les mandats SEPA renseignés sont amendés avec le nouveau compte bancaire.
Touts les contrats utilisant l'un des mandats SEPA après la date de signature de la mobilité bancaire est mis à jour avec un avenant de modification de coordonnées bancaires.