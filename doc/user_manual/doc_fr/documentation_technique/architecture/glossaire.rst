Glossaire
=========

Cette page a pour objet de regrouper un lexique des différents termes liés à
**Coog** avec leur siginification « habituelle ». En général un champ contenant
ce / ces mots sera une référence (un *Many2One*) vers un objet de ce type.

Données Tiers
-------------

- ``party`` / ``party.party`` : un tiers (personne physique ou morale)
- ``address`` / ``party.address`` : une adresse rattachée à un tiers

Données contrat
---------------

- ``contract`` : le contrat d'assurance
- ``covered`` / ``covered_element`` / ``contract.covered_element`` : le risque
  couvert par le contrat (la personne / la voiture / etc.)
- ``option`` / ``contract.option`` : la garantie souscrite sur le contrat
  d'assurance
- ``extra_data`` : les « données complémentaires » issues du paramétrage
- ``loan`` un prêt couvert dans le cadre d'un contrat emprunteur
- ``premium`` / ``contract.premium`` : une information de tarif stockée sur le
  contrat, utilsiée pour ensuite générer les quittances
- ``billing_information`` / ``contract.billing_information`` : les données de
  facturation du contrat (compte bancaire, fréquence, etc.)
- ``loan`` : Un prêt, utilisé pour les contrats d'assurance emprunteur
- ``share`` / ``loan_share`` / ``loan.share`` : Une quotité de prêt, autrement
  dit à quel pourcentage un prêt donné est couvert pour une garantie donnée
- ``underwriting`` / ``contract.underwriting`` : Une analyse de risque lors de
  la souscription

Données sinistre
----------------

- ``claim`` : un dossier sinistre
- ``loss`` / ``claim.loss`` : Le préjudice à l'origine du sinistre. Contiendra
  notamment, outre la date de survenance, le type d'événement ainsi que le type
  de préjudice
- ``loss_desc`` / ``benefit.loss_desc`` : Un type de préjudice. Par exemple,
  « Arrêt de travail », « Décès », etc.
- ``event_desc`` / ``benefit.event_desc`` : Un événement / fait générateur. Il
  s'agit concrètement de la cause du préjudice. Par exemple « Maladie », «
  Accident », etc.
- ``service`` / ``claim.service`` : Une prestation pour un préjudice. Par
  exemple, pour un préjudice de type « Décès », on pourra avoir comme
  prestations un capital, une rente conjoint, une rente éducation, etc... Les
  prestations sont calculées automatiquement à partir des contrats souscrits
  par la personne concernée par le sinistre
- ``indemnification`` / ``claim.service.indemnification`` : Un remboursement
  pour une prestation. Certaines prestations ne donneront lieu qu'à un seul
  versement (ex : Capital décès), d'autres seront récurrentes (Arrêts de
  travail, rentes, etc.)
- ``beneficiary`` / ``claim.service.beneficiary`` : Un bénéficiaire, nommé,
  d'une prestation. Principalement utilisé en cas de décès, où l'assuré ne peut
  pas être lui-même bénéficiaire

Données de paramétrage
----------------------

- ``product`` / ``offered.product`` : le produit souscrit sur un contrat
- ``coverage`` / ``offered.option.description`` : la description de la garantie
  souscrite
- ``item_desc`` / ``offered.item.description`` : la description du risque
  couvert
- ``benefit`` : un type de prestation sinistre

Données comptabilité
--------------------

- ``invoice`` / ``account.invoice`` : si rattachée à un contrat, une quittance
  à prélever au titre du contrat. Si à un sinistre, un remboursement effectué
  dans le cadre de ce sinistre
- ``invoice_line`` / ``account.invoice.line`` : ligne (élément constituant)
  d'une quittance / facture
- ``move`` / ``account.move`` : toute opération comptable. En général (mais pas
  toujours) rattaché à une quittance
- ``move_line`` / ``account.move.line`` : ligne comptable
- ``account.payment`` / ``payment`` : un prélèvement ou un virement SEPA. Peut
  également être associé à d'autres modes de paiement (paybox, etc.)

Commissionnement
----------------

- ``commission`` : une ligne de commission, en général rattachée à une ligne de
  quittance
- ``commission.plan`` / ``plan`` : un plan de commissionnement, le descriptif
  du mode de calcul des commissions pour une ou plusieurs garanties
- ``commission.agent`` / ``agent`` : un protocole de commissionnement, un
  contrat entre la société et le courtier
- ``distribution.network`` / ``dist_network`` / ``network`` : un noeud du
  réseau de distribution. Peut être un courtier
- ``broker`` (comme nom de variable / nom de champ) : un courtier

Champs « classiques »
---------------------

- ``start`` / ``start_date`` / ``date`` : Date de prise de valeur d'un objet
  versionné (ou tout simplement ayant une date d'effet)
- ``end`` / ``end_date`` : Date de fin de valeur d'un objet versionné
- ``extra_data`` : Valeurs de données complémentaires (cf. documentation
  administration pour une explication détaillée des sur le sujet)
- ``company`` : La société utilisatrice de **Coog**. Concrètement, **Coog** ne
  supporte pas d'avoir plus d'une *Company* pour une base de donnée, donc ce
  champ aura la même valeur partout
- ``rule_engine`` / ``rule`` : Un lien vers une règle métier décrite via un
  algorithme saisi dans l'application (cf documentation administration
  correspondante)
