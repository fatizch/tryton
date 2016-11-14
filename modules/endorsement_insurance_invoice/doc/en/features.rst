- **Avenant unitaire de manipulation des données de quittancement :** Permet de
  modifier sur un contrat les paramètres de quittancement. Ces modifications
  peuvent être prévues dans le futur, et porter sur la fréquence, le mode de
  paiement, le compte à utiliser, etc...

- **Notion d'avenant tarifant :** Il est possible de marquer un avenant comme
  *tarifant*. Cela signifie que :

 - L'application de l'avenant déclenchera un recalcul des tarifs sur le
   contrats à partir de la date d'effet

 - Ce recalcul sera suivi d'une suppression / annulation des quittances
   antérieures à ou incluant la date d'effet de l'avenant, en fonction de leur
   statut (les quittances en brouillon ou simplement validée seront supprimées,
   celles émises ou payées seront annulées, et la comptabilité sera mise à jour
   en fonction).

 - Les quittances seront ensuite recréées / émises pour prendre en compte les
   nouveaux tarifs.

 - Tout ces comportement seront répliqués en cas d'annulation de l'avenant.

 Il est important de noter que les avenants tarifants forcent la génération
 d'une quittance débutant à leur date d'effet.
