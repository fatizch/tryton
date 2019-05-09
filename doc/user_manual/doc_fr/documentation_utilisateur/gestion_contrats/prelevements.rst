Prélèvements
============

Les prélèvements sont un mode de paiement particulier, dans le sens où ils sont
initiés par **Coog**, plutôt que par le client final. Ce document à pour
objectif de présenter la cinématique des prélèvements dans **Coog**, et la
façon dont ils intéragissent avec les quittances et les contrats.

Génération
----------

Les prélèvements sont dans la grande majorité des cas générés automatiquement
via des traitements batch. Concrètement, une quittance « Émise » donne lieu à
la création d'un paiement si les conditions suivantes sont satisfaites :

- Le mode de quittancement du contrat à la date de début de la quittance est en
  prélèvement
- La date de paiement sur la ligne à payer de la quittance (calculée à partir
  du jour de prélèvement sélectionné à la souscription) est passée
- Il y a un mandat SEPA valide sur le contrat à la date de prélèvement
- Le statut du contrat ne demande pas la suspension des prélèvements
- Les prélèvements n'ont pas été suspendu suite à de trop nombreux rejets (cf
  infra)

Les paiements générés sur un contrat prennent en compte le montant disponible
sur le solde du Tiers payeur du contrat lors de leur génération. Autrement dit,
si on génère un prélèvement pour une quittance de 100 €, pour un Tiers
disposant de 20 € disponibles suite à des opérations passées, le prélèvement
généré pour cette quittance sera de 80 €.

Traitement
----------

Une fois les prélèvements générés pour tous les contrats à une date donnée, ils
sont agrégés dans un « Groupe de paiement ». Cette notion correspond à peu de
choses près dans ce contexte à une bande de prélèvement SEPA.

Une fois intégré à une bande de prélèvement, il n'est plus possible
d'intervenir sur le paiement individuellement. En effet, la constitution du
groupe correspond à la génération d'un fichier à destination de la banque. Il y
a donc un risque de généré des incohérences entre ce qui a été transmis et ce
qui est enregistré dans **Coog**.

À ce moment, les prélèvement sont en cours de traitement, mais les quittances
ne sont toujours pas « Payées », étant donné qu'aucune comptabilité n'a été
générée, et donc aucune réconciliation n'a été faite.

Automatiquement lors du passage de la date de prélèvement, ou manuellement via
une action sur le groupe de paiement (« Accuser réception »), **Coog** va
générer cette comptabilité. Chaque prélèvement va donner lieu à une opération
comptable sur le compte du tiers associé, et si possible (la quittance peut
avoir été annulée entre temps) la ligne de prélèvement et la ligne à payer de
la quittance seront réconciliées, ce qui passera la quittance à l'état
« Payée ».

Rejets
------

Les rejets de prélèvement peuvent être intégrés de plusieurs façon différentes
dans **Coog** en fonction de la nature des informations disponibles et du
niveau d'intégration dans le Système d'Information du client :

- Automatiquement par traitement batch, à partir de fichiers déposés à un
  emplacement pré-configuré sur le serveur applicatif
- Manuellement via l'intégration manuelle du fichier de rejet dans **Coog**
- Manuellement via le rejet, un par un, des prélèvement concernés (saisie
  manuelle de motifs)

Lors d'un rejet de prélèvement, **Coog** consulte la configuration du *Journal
de paiement* rattaché au prélèvement pour déterminer les actions à mener. En
fonction du motif de rejet, ainsi que de sa fréquence (il est possible de
paramétrer certaines actions dans le cas où un motif de rejet donné se
re-présentait plusieurs fois d'affilé), les actions correspondantes seront
jouées. Ces actions peuvent être (liste non exhaustive, dépendant des modules
installés) :

- Passage en paiement par chèque
- Représentation immédiate
- Représentation différée
- Suspension des prélèvements (le contrat devra être dé-suspendu manuellement)
- Suspension des prélèvements (le contrat sera dé-suspendu dès que la quittance
  ayant généré le prélèvement fautif sera payée)

Il est également possible de déclencher l'envoi d'un courrier / email, ainsi
que l'ajout de frais de rejets qui seront demandés en sus de la quittance
initiale.
