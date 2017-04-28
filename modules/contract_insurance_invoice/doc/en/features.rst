- **Payment suspensions :** It is now possible to suspend the payments for a
  given contract billing information. These suspensions could be automatics 
  (Actuib defined in a journal failure action) or manuals via a button in the 
  contract billing informations list page. The un-suspension can also be
  automatic (suspension is inactive when the associated account move line
  is reconciled) or manual (The same way as the manual suspension).
  A relate is added on billing informations to easely find associated suspensions.
  Finally, a new page showing all contracts with a suspended billing information
  has been added to the contract list view.

- **Paramétrage des paramètres de quittancement :** Il est possible de définir
  par paramétrage un ensemble de règles de quittancement, ainsi que les
  produits et / ou conditions sous lesquelles ces règles sont disponible.
  Ces règles contiennent typiquement le moyen de paiement utilisé et la
  fréquence de quittancement.

- **Gestion des paramètres de quittancement :** Les contrats nécessitent que
  des paramètres de quittancement soient renseignés, afin que le système soit
  capable de décider quand et comment générer les quittances. Ces paramétres
  sont limités à ceux disponibles pour le produit sélectionné sur le contrat.

- **Branchement de la comptabilité :** A partir du moment où des quittances
  sont générées, il est nécessaire de les comptabiliser. Les données de
  paramétrage pur (Produits, Garanties offertes, Frais...) requièrent
  maintenant de renseigner les comptes comptables à utiliser lors des
  opérations de quittancement.

- **Quittances d'assurance :** Les quittances d'assurance comportent des
  informations supplémentaires par rapport aux quittances *standard*.
  En particulier, elles sont rattachées à une période de couverture sur le
  contrat qui les a générées. De plus, on introduit la séparation des montants
  de frais.

- **Détails de quittance :** Afin de comprendre précisément l'origine de
  chaque ligne des quittances générées, les lignes des quittances générées
  suite à une facturation de contrat ont des *détails* qui relie la ligne aux
  données métier qui l'ont généré. Ceci permet également de faciliter les
  extractions basées sur les primes.

- **Modification de compte bancaire :** Permet de modifier le compte bancaire
  à utiliser pour le quittancement sur un contrat, et de le propager aux
  contrats qui utilisaient le même compte.

- **API de tarification :** Il est possible d'obtenir via un appel RPC
  les tarifs pour un contrat potentiel. Rien n'est sauvegardé en base.

- **Taxes incluses :** Il est possible de définir dans le paramétrage que la
  prime est définie taxes incluses ou taxes exclues. Cette option n'est
  disponible au niveau d'un produit que si la stratégie d'arrondi définie dans
  la configuration est l'arrondi par ligne.

- **Comptabilité par contrat :** Les lignes de mouvement comptable rattachées à
  un contrat sont liées à ce contrat. Ce lien est propagé par les
  reconciliations (autrement dit, les lignes réconciliant des lignes rattachées
  à un contrat sont rattachées à ce contrat), à condition qu'il n'y ait pas
  d'ambigüité sur le contrat concerné.

- **Réconciliation plus flexible :** Il est maintenant possible lors des
  opérations de réconciliation de transférer un éventuel reste sur un compte
  tiers, voire de le rattacher à un contrat.

- **Epuisement du trop perçu par quittancement:** Un traitement par batch
  est désormais disponible pour permettre d'épuiser le trop perçu d'un contrat
  par lettrage avec des quittances générées pour le futur.
