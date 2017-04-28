- **Génération des bordereaux assureurs** : La génération se base sur le compte
  d'attente défini au niveau de l'assureur. Pour chaque ligne dans ce compte,
  la commission du gestionnaire est calculée. Un mouvement comptable est généré
  qui décroit le montant du compte d'attente du montant de la ligne et crédite
  le compte de produit du montant de la commission, le reste va dans le compte
  à payer de l'assureur.

- **Compte d'attente assureur** : Les assureurs ont un compte d'attente qui est
  utilisé pour créer et identifier les lignes des bordereaux assureurs. Ce
  compte est habituellement alimenté par les mouvements de liées aux factures
  client

- **Batch de génération des bordereaux assureurs** : La génération des
  bordereaux assureurs peut être assez longue, en particulier pour les
  assureurs rattachés à des milliers de contrats. Des batchs sont à disposition
  pour effectuer ces traitements de manière optimisée
