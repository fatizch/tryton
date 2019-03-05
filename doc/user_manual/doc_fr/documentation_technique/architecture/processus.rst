Process métiers
===============

Nous allons ici détailler les différents processus métiers utilisables dans
l'application. Étant donné la nature paramétrable des processus dans **Coog**,
le détail exact des étapes présentées pourra varier, mais les grandes lignes
seront globalement les mêmes.

Nous prendrons exemple sur les processus définis dans la base généré
automatiquement à l'aide de la commande ``coog db demo``.

Souscription contrat
--------------------

Le processus le plus souvent utilisé dans **Coog** est la souscription de
contrats. Bien que son apparence, son contenu, voire même sa longueur puisse
varier en fonction des clients ou des produits, il comporte un certain nombre
d'éléments clés que l'on retrouvera quasi-systématiquement :

- Informations de base
- Saisies des risques
- Choix des garanties
- Analyse de risque (éventuellement)
- Documents requis
- Informations de facturation
- Validation

La souscription est lancée via l'assistant ``Souscription contrat`` disponible
dans le menu ``Contrat``.

Informations de base
~~~~~~~~~~~~~~~~~~~~

Les premières informations, nécessaires pour souscrire un contrat, seront :

- Date d'effet (``initial_start_date``)
- Produit (``product``)
- Souscripteur (``subscriber``)
- Données complémentaires du contrat (``extra_data_values``)

Selon les modules installés, on pourra également retrouver :

- Portefeuille (``portfolio``), le « portefeuille client » auquel sera rattaché
  le contrat
- Le distributeur (``dist_network``), qui correspond à l'entité (courtier,
  vendeur, site web, etc.) ayant « apporté » l'affaire

Saisie des risques
~~~~~~~~~~~~~~~~~~

La seconde étape est la saisie des risques assurés sur le contrat. En fonction
des produits, il est possible que par défaut un risque soit créé
automatiquement à partir du souscripteur (dans le cas de contrats préovyance /
santé / emprunteur, dans 90 % des cas le souscripteur sera un des assurés).

Il sera toujours possible de rajouter des risques à la main, et il faudra dans
tous les cas saisir les *données complémentaires* qui auront été
automatiquement calculées à partir du descripteur de risque (``item_desc``,
calculé automatiquement à partir du produit).

Dans le cas de contrats emprunteurs, on pourra également à cette étape créer /
sélectionner les prêts qui seront utilisés sur le contrat.

Choix des garanties
~~~~~~~~~~~~~~~~~~~

Lors de la saisie des risques, les garanties « obligatoires » seront
automatiquement sélectionnées sur chacun des risques couverts. Dans le cas où
il y a des garanties optionnelles, ou si l'on souhaite dé-sélectionner une
garantie optionnelle mais pré-cochée, cette étape donne accès à un assistant
permettant de le faire.

Dans le cas de contrats emprunteur, c'est également à cette étape que se fera
le rattachement des prêts aux différentes garanties, avec les quotités
correspondantes.

En outre, cette étape permet également la saisie des données complémentaires
rattachées aux différentes garanties, ainsi que certaines informations liées
aux garanties dépendant du produit souscrit :

- Montant de couverture (``coverage_amount``)
- Clauses bénéficiaires et bénéficiaires (``benficiary_clause`` /
  ``beneficiaries``)
- Surprimes (``extra_premium``)
- Exclusions (``exclusions``)

En sortie de cette étape, il y aura en général une première vague de contrôles
automatiques basées sur les règles de paramétrage d'éligibilité des garanties.
Par exemple, si on a configuré qu'une personne de plus de 80 ans ne pouvait pas
être couvert par une garantie donnée, c'est à ce moment que l'utilisateur en
sera informé.

Analyse de risque
~~~~~~~~~~~~~~~~~

Pour certains produits, en général couvrant des risques de santé pour des
capitaux potentiellement élevés (prévoyance / emprunteur), l'étape d'« Analyse
de risque » correspond à une analyse du dossier par un médecin afin de
déterminer si les assurés sont compatibles avec le profil de risque pour ce
produit. Par exemple, dans le cas où un assuré a des antécédents de problèmes
cardiaques, cette étape conduira :

- Ou bien au refus de l'assurer
- À l'ajout d'exclusions pour les risques cardiaques sur une ou plusieurs
  garanties
- À l'ajout de surprimes visant à compenser le risque supplémentaire

Cette étape fait partie de celles qui peuvent être totalement absente d'un
processus, si l'assureur estime qu'il n'y en pas besoins (montants faibles, ou
risques non liés (ou très peu) à la santé des assurés).

Documents requis
~~~~~~~~~~~~~~~~

Si le paramétrage produit le requiert (et c'est le cas dans la majorité des
produits), la souscription du contrat nécessitera la réception de documents
signés par le souscripteur et / ou les assurés avant de pouvoir être finalisée.

Cette étape permet au gestionnaire de visualiser la liste des pièces
nécessaires, ainsi que de noter celles qui ont bien été reçues. Selon le
paramétrage de l'application il sera nécessaire de saisir la date de réception
(``reception_date``) du document, voire de le saisir dans l'outil de *Gestion
Électronique de Documents* (GED) intégré à **Coog**.

Il sera en général impossible d'avancer dans la souscription tant que tous les
documents requis n'ont pas été « reçus ».

Informations de facturation
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Cette étape regroupe en général la saisie des informations de quittancement
(``billing_informations``) ainsi que la visualisation et l'éventuelle
modification des frais rattachés au contrat.

Il s'agit en général de la dernière étape de saisie de la souscription (la
dernière étape ayant en général pour but de présenter un récapitulatif avant
activation). En sortie de cette étape seront en général recalculées les primes,
et l'utilisateur pourra consulter les tarifs calculés ainsi qu'une simulation
de l'échéancier du contrat.

Validation
~~~~~~~~~~

La dernière étape offre une dernière vision de contrôle du contrat, avant
l'activation finale. Il n'est pas rare qu'une validation soit opérée par un
autre gestionnaire, afin de s'assurer de l'exactitude des données saisies.

Lors de l'activation du contrat, **Coog** va en général :

- Passer le statut du contrat à *Actif*
- Recalculer les primes
- Générer la première quittance (paramétrable)
- Générer des documents (typiquement le *Certificat d'adhésion*) qui seront
  envoyés au souscripteur
