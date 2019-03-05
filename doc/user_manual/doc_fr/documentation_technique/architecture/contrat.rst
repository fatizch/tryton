Contrat
=======

Structure de base
-----------------

La structure « de base » d'un contrat est la suivante::

 +----------------------+
 |                      |--------> product : many2one
 |  Contrat [contract]  |
 |                      |--------> subscriber : many2one
 +----------------------+
       |
       | covered_elements : one2many
       |   (contract : many2one)
       |
       |      +---------------------------------------------+
       |      |                                             |--------> item_desc : many2one
       +----->+  Risque couvert [contract.covered_element]  |
              |                                             |--------> party : many2one
              +---------------------------------------------+
                  |
                  | options : one2many
                  |   (covered_element : many2one)
                  |
                  |      +----------------------------------------+
                  |      |                                        |
                  +----->+  Garantie souscrite [contract.option]  |--------> coverage : many2one
                         |                                        |
                         +----------------------------------------+

Chaque élément du contrat (et c'est le cas de nombreux éléments métiers
importants dans **Coog**) est rattaché à l'élément de paramétrage
correspondant :

- Le contrat au Produit ``offered.product``
- Le risque couvert au Descripteur de Risque ``offered.item.description``
- La garantie souscrite à la garantie offerte ``offered.option.description``

**Un contrat n'est directement éditable que dans le cas où son ``statut`` est
*Devis*. Tous les champs du contrat ainsi que ceux de ses « sous-objets »
(``One2Many``s) ont un ``states`` pour les rendre ``readonly`` dès lors que le
statut du contrat ne le permet pas**

Champs du contrat
-----------------

Le contrat est lui-même composé de plusieurs parties ::

   +----------------------+
   |                      |
   |  Contrat [contract]  |
   |                      |
   +----------------------+
      |
      | activation_history : one2many
      |
      |     +---------------------------------------------------------+
      |     |                                                         |
      +---->+  Historique d'activation [contract.activation_history]  |
      |     |                                                         |
      |     +---------------------------------------------------------+
      |
      | options : one2many
      |
      |     +----------------------------------------+
      |     |                                        |
      +---->+  Garantie souscrite [contract.option]  |
      |     |                                        |
      |     +----------------------------------------+
      |
      | billing_informations : one2many
      |
      |     +---------------------------------------------------------+
      |     |                                                         |
      +---->+  Données de facturation [contract.billing_information]  |
      |     |                                                         |
      |     +---------------------------------------------------------+
      |
      | extra_datas : one2many
      |
      |     +---------------------------------------------+
      |     |                                             |
      +---->+  Données versionnées [contract.extra_data]  |
      |     |                                             |
      |     +---------------------------------------------+
      |
      | fees : one2many
      |
      |     +------------------------+
      |     |                        |
      +---->+  Frais [contract.fee]  |
            |                        |
            +------------------------+

Tous ces ``One2Many`` ont comme champ inverse un ``ManY2One`` nommé
``contract``.

Historique d'activation et date d'effet du contrat
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comme expliqué dans la section *Assurance*, certains types de contrats peuvent
avoir une durée figée (typiquement un an), mais être renouvelés une ou
plusieurs fois. Pour certains produits (auto, habitation, prévoyance), il
s'agit du fonctionnement standard.

Pour gérer ce comportement, **Coog** utilise une entité séparée du contrat,
l'*Historique d'activation*, pour garder la trace des différents
renouvellements.

Le corollaire de cette approche est que les dates de début et de fin du contrat
sont calculés automatiquement à partir de cet historique, et ne sont donc pas
stockés directement sur le contrat :

- ``start_date`` : date de début de l'``activation_history`` valide à la date
  du jour
- ``end_date`` : date de fin de l'``activation_history`` valide à la date du
  jour
- ``initial_start_date`` : minimum des dates de début. Il s'agit de la date à
  laquelle le contrat a été actif pour la première fois
- ``final_end_date`` : maximum des dates de fin, à partir du moment où le
  contrat n'est plus renouvellé. Autrement dit, ce champ est vide si le contrat
  sera encore renouvellé au moins une fois

Du fait de la nature de ces champs, les champs ``start_date`` et ``end_date``
ne doivent **quasiment jamais** être utilisé dans du code métier. En effet, ils
dépendent de la date du jour, et ne sont donc pas « fiables » dans le sens où
leur valeur change au cours du temps.

Garanties souscrites
~~~~~~~~~~~~~~~~~~~~

Le modèle ``contract.option`` (garantie souscrite) est un peu particulier en
cela qu'il peut être rattaché ou bien directement à un contrat, ou bien à un
risque couvert.

Pour le cas des risques couverts, il y a davantage de détails dans la section
dédiée. Pour faire simple, il s'agit des garanties qui portent directement sur
le risque assuré.

Dans le cas des contrats, il s'agit de garanties « globales » sur le contrat.
Ces garanties ont en général un tarif fixe, indépendament du nombre de risques
couverts par le contrats. Le cas « classique » est celui des garanties ditest
« d'assistance », qui donne droit moyennant le paiement d'une cotisation
forfaitaire à une assistance en cas de sinistre (le détail dépendant du type de
contrat concerné).

Données de facturation
~~~~~~~~~~~~~~~~~~~~~~

Les informations de facturation (permettant de déterminer quand et comment
est-ce que le contrat doit être payé) sont stockées dans un modèle séparé,
``contract.billing_information``. La raison principale est que ces informations
peuvent évoluer au cours du temps, et que l'on souhaite garder l'historique des
modifications afin que le contrat reste cohérent à tout instant.

Les données portées par ce modèle seront notamment :

- ``date`` : la « date de valeur », utilisée pour déterminer quel
  ``billing_information`` est actif à une date donnée
- ``payer`` : la personne qui va effectivement payer le contrat. Dans la
  majorité des cas il s'agira du souscripteur du contrat, mais il y a quelques
  cas où l'on souhaite utiliser le compte bancaire d'une autre personne
  (typiquement celui du conjoint)
- ``billing_mode`` : le « mode de quittancement » du contrat, un élément de
  paramtrage qui contient à la fois la fréquence (mensuel, trimestriel, etc.)
  ainsi que le mode de paiement (prélèvement automatique ou « manuel »,
  typiquement par chèque)
- ``payment_term`` : les conditions des paiement. Dans 95 % des cas, il s'agira
  d'un paiement comptant à la date de valeur de la quittance, mais pour
  certains produits (vendus à des entreprises par exemple), on peut souhaiter
  permettre un règlement différé de 2 mois par exemple
- ``direct_debit_account`` / ``sepa_mandate`` : dans le cas classique des
  règlements par prélèvement automatique, ces champs contiennent respectivement
  le compte bancaire à utiliser, ainsi que la référence du *Mandat SEPA* signé
  par le souscripteur pour le prélèvement
- ``direct_debit_day`` : permet d'indiquer quel jour du mois les prélèvements
  doivent avoir lieu pour ce contrat

Afin de faciliter la lecture (et la saisie), le champ ``billing_information``
sur le contrat permet d'afficher directement la version courante (valide à la
date du jour) des ``billing_informations``.

Données versionnées
~~~~~~~~~~~~~~~~~~~

Le contrat dispose de certaines informations « statiques » (produit,
soucripteur, etc.) qui n'ont pas vocation à évoluer au cours du temps, mais
également des informations versionnées. Ces informations sont séparées dans un
modèle séparé, ``contract.extra_data``.

Les champs que l'on y trouve sont :

- ``date`` : La « date de valeur » utilisée pour déterminer la version
  applicable à une date donnée
- ``extra_data_values`` : Les valeurs de données complémentaires pour le
  contrat à cette date

Pour l'instant, il s'agit de la seule informations stockée « en standard » sur
ce modèle , mais cela sera probablement amené à évoluer. Il sera peut-être
renommé un jour pour mieux refléter le fait qu'il ne concerne pas que les
données complémentaires.

Afin de faciliter la saisie, un champ ``extra_data_values`` est directement
disponible sur le contrat pour afficher et alimenter automatiquement la version
de la date du jour.

Risque couvert
--------------

Le risque couvert décrit ce qui est assuré par le contrat (il peut s'agir d'une
personne ou d'un objet, voir quelque chose d'abstrait) ::

   +--------------------------------------------+
   |                                            |
   |  Risque couvert [contract.covered_element] |---------> party
   |                                            |
   +--------------------------------------------+
     |
     | options : one2many
     |
     |   +----------------------------------------+
     |   |                                        |
     +-->+  Garantie souscrite [contract.option]  |
     |   |                                        |
     |   +----------------------------------------+
     |
     | versions : one2many
     |
     |   +----------------------------------------------------------+
     |   |                                                          |
     +-->+  Données versionnées [contract.covered_element.version]  |
     |   |                                                          |
     |   +----------------------------------------------------------+
     |
     | sub_covered_elements : one2many
     |
     |   +-------------------------------------------+
     |   |                                           |
     +-->+  Sous-risques [contract.covered_element]  |
         |                                           |
         +-------------------------------------------+

La particularité principale du risque couvert est qu'il s'agit d'une structure
arborescente (plus de détails ci-dessous).

Le modèle ``contract.covered_element`` lui-même contient les éléments
suivants :

- ``item_desc`` : le lien vers la « description » du risque. Il y a davantages
  de détails dans la section de la documentation consacrée au paramétrage, mais
  concrètement cela permet de connaître les informations nécessaires pour
  décrire le risque
- ``party`` : dans le cas où l'``item_desc`` le requiert (c'est le cas de tous
  les produits *Préovyance*, *Emprunteur* et *Santé*), il s'agit d'un lien vers
  une personne physique. Ce seront alors les événements affectant cette
  personne précise qui déclencheront d'éventuels sinistres et indemnisations)

Les champs ``manual_start_date``, ``manual_end_date`` et ``end_reason`` ne sont
utilisés que dans le cas de *sous-risques* et sont détaillés ci-dessous.

Garanties souscrites
~~~~~~~~~~~~~~~~~~~~

De façon générale, quand on parlera de *garanties* sur un contrat, on pensera
par défaut aux garanties rattachées à des risques couverts plutôt qu'à des
garanties directement liées au contrat (cf ci-dessus).

Le modèle ``contract.option`` sera détaillé dans une section dédiée, mais il y
a toutefois quelques informations spécifiques aux garanties liées aux risques
couverts à donner ici :

- Les risques couverts n'ont pas de dates de début / de fin stockées
  directement (les champs ``manual_*`` sont réservées aux sous-risques). Ce qui
  donne la date de « validité » d'un risque est la période pendant laquelle il
  est couvert par au moins une garantie. Les champs ``start_date`` et
  ``end_date`` sont des champs fonction alimentés automatiquement à partir de
  là
- La liste des garanties se retrouve concrètement dans trois champs. Le champs
  habituellement utilisé est ``options``, parce que c'est celui qui contient
  les garanties souscrites sur le contrat. Les autres sont
  ``declined_options`` (les garanties qui ont été souscrites, mais finalement
  déclinées et donc jamais actives) et ``all_options`` qui contient la somme
  des deux autres

Données versionnées
~~~~~~~~~~~~~~~~~~~

Le modèle ``contract.covered_element.version`` joue le même rôle pour le risque
couvert que ``contract.extra_data`` pour le contrat. Concrètement, il a pour
objet de conserver un historique de modifications pour certaines données
rattachées au risque.

On y retrouve donc :

- Un champ ``date`` pour gérer l'historisation
- Un champ ``extra_data`` pour conserver les données complémentaires rattachées
  au risque

Comme c'est le cas pour les contrats, l'information « intéressante » (ici le
contenu du champ ``extra_data``) est directement accessible depuis le contrat
via le champ fonction ``current_extra_data``.

Sous-risques
~~~~~~~~~~~~

Pour certains types de produits (assurance collective prévoyance / santé,
flotte auto, etc.), le nombre de risques assurés peut très vite devenir élevé
(plusieurs centaines voire milliers). En outre, étant donné les montants mis en
jeu, il est fréquent que ces contrats donnent lieu à des négociations
permettant d'affiner au mieux leurs caractéristiques en fonction des besoins de
la société souscriptrice.

Afin de faciliter la saisie et la compréhension de ces contrats, les risques
assurés sont fréquemment regroupés en « macro-risques ». Par exemple, dans le
cadre des contrats d'assurance collective prévoyance, les employés de la
société souscriptrice seront fréquemment regroupés par catégorie : Cadres,
Non-Cadres, Externes, Intérimaires, etc.

Concrètement, dans ce cas les ``covered_element`` directement rattachés aux
contrats seront ces « catégories », et le détail des personnes assurées
(généralement appelés les *Affiliés*, ou *Adhérents* du contrat) seront
enregistrés un niveau « en dessous » de ces catégories.

En théorie, il peut y avoir plusieurs niveaux de regroupement. Le lien entre
ces différents niveaux se fait via le champ ``parent``, qui s'il est renseigné
(il ne l'est pas pour les risques directement rattachés au contrat) permet
d'identifier le groupe auquel appartient un sous-risque.

La logique de cette hiérarchisation est que chaque sous-risque est assuré par
les garanties de son / ses parents (ce qui évite de dupliquer les
``contract.option`` pour chacun d'entre eux).

Par ailleurs, les sous-risques disposent de quelque champs qui leur sont
spécifiques (i.e. qui sont en général ignorés dans le cas de risques
directement rattachés aux contrats) :

- ``manual_start_date`` : La date à laquelle un sous-risque a été rattaché au
  risque parent
- ``manual_end_date`` : La date à laquelle un sous-risque est éventuellement
  « sorti » du risque principal
- ``end_reason`` : Le motif de sortie si applicable

:Note: Techniquement, ces risques et sous-risques sont stockés à l'aide d'un
       algorithme spécial utilisant les champs ``left`` et ``right`` pour
       faciliter les recherches de parents

Garanties souscrites
--------------------

La *Garantie* est l'élément constitutif central du contrat. Un contrat n'existe
concrètement que via ses garanties.

Autrement dit, un contrat sans garanties actives à une date n'a pas de sens (et
n'est pas censé exister dans **Coog**).

Une garantie contient les éléments suivants::

   +----------------------------------------+
   |                                        |
   |  Garantie souscrite [contract.option]  |--------> coverage
   |                                        |
   +--+-------------------------------------+
      |
      |  versions : one2many
      |
      |   +-------------------------------------------------+
      |   |                                                 |
      +-->+  Données versionnées [contract.option.version]  |
      |   |                                                 |
      |   +-------------------------------------------------+
      |
      |  extra_premiums : one2many
      |
      |   +---------------------------------------------+
      |   |                                             |
      +-->+  Surprimes [contract.option.extra_premium]  |
      |   |                                             |
      |   +---------------------------------------------+
      |
      |  beneficiaries : one2many
      |
      |   +-----------------------------------------------+
      |   |                                               |
      +-->+  Bénéficiaires [contract.option.beneficiary]  |--------> party
      |   |                                               |
      |   +-----------------------------------------------+
      |
      |  loan_shares : one2many
      |
      |   +-------------------------+
      |   |                         |
      +-->+  Quotités [loan.share]  |---------> loan
          |                         |
          +-------------------------+

La *Garantie souscrite* contient les champs « importants » suivants :

- ``coverage`` : le lien vers la *Garantie offerte*, qui correspond à la
  configuration fonctionnelle de la garantie. C'est là que l'on va retrouver
  l'ensemble des règles de calcul / de gestion à appliquer pour cette garantie.
  Le détail de se paramétrage se trouve dans la section portant sur le
  paramétrage produit
- ``start_date`` / ``end_date`` : les dates pendant laquelle la garantie est
  active. Ces dates sont des champs fonction, calculés à partir des éléments
  suivants :

     * Date d'effet initial du contrat
     * Date de fin « finale » (dernier renouvellement) du contrat
     * ``manual_start_date`` / ``manual_end_date`` : renseignés dans le cas où
       le client a expressément demandé des modifications sur son contrat
     * ``automatic_end_date`` : la date de fin automatiquement calculée pour la
       garantie. Concrètement, cette date est calculée lors de l'activation du
       contrat, et après certains avenants. Par exemple, elle correspondra en
       général  à la date de fin du dernier prêt couvert par la garantie pour
       les contrats emprunteur

- ``extra_premiums`` : Dans certains cas, l'assureur peut imposer au
  souscripteur des *Surprimes*, autrement dit après analyse du dossier décider
  que le risque est trop grand et qu'il doit être compensé par une cotisation
  plus élevée. Ce champ permet de stocker ces augmentations (ou réductions !)
  tarifaires
- ``beneficiaries`` : Sur certaines garanties, notamment celles couvrant le
  Décès d'une personne physique, il est nécessaire de préciser qui bénéficiera
  des indemnisations versées par l'assureur. Ce champ permet, en conjonction
  avec le champ ``beneficiary_clause`` (Many2One vers le modèle ``clause``), de
  stocker lors de la souscription la liste des personnes bénéficiaires
  (directement via leur nom / prénom etc., ou indirectement avec des clauses
  « génériques » de type 'Mon conjoint, à défaut mes enfants par parts égales')
- ``loan_shares`` : Uniquement dans le cas de contrats emprunteur, permet de
  spécifier pour cette garantie quels sont les prêts couverts et à quelle
  hauter. Plus de détails se trouvent dans la section dédiée aux prêts

Versions
~~~~~~~~

Comme pour le contrat et les risques couverts, il est nécessaire de stocker
certaines informations de façon versionnée sur les garanties. Ces informations
sont susceptibles d'évoluer dans le temps à la demande du souscripteur, ou du
fait d'évolutions des conditions générales du contrat.

On y retrouve notamment :

- ``date`` : La « date de valeur » utilisée pour déterminer la version
  applicable à une date donnée
- ``extra_data`` : les données complémentaires applicables pour cette version
- ``coverage_amount`` : Pour certains types de contrat, on souhaite stocker
  directement un « Montant de couverture ». Ce montant, qui peut évoluer suite
  à des modifications demandées par le souscripteur, correspond en général au
  montant qui sera reversé (en capital, ou périodiquement) si la garantie
  devait être activée suite à un sinistre
- ``extra_details`` : Permet de stocker des données métier calculées à la volée
  aux utilisateurs

Afin de faciliter la saisie, des champs fonction ``current_extra_data`` et
``current_coverage_amount`` sont définis sur les garantie.

Données de prêts
~~~~~~~~~~~~~~~~

Dans le cas de l'assurance emprunteur (et uniquement dans ce cas), le contrat
peut être adossé à un ou plusieurs prêts. Le modèle ``loan`` contient la
description des données du prêt effectué auprès d'une banque (durée, taux,
fréquence de remboursements, etc.) et est capable de calculer l'échéancier pour
toute sa durée.

Une fois les données des prêts saisies, ils sont rattachées aux différentes
garanties via le modèle ``loan.share``.

Concrètement, un contrat peut couvrir plusieurs personnes (``covered_element``,
ou « risques couverts »), pour plusieurs garanties (``options``), pour
plusieurs prêts (``loan``).

Il est donc nécessaire pour chaque garantie de définir quels sont les prêts
qu'elle « prend en charge ». Le modèle ``loan.share`` contient les informations
suivantes :

- ``loan`` : un lien vers le prêt concerné
- ``share`` : la « quotité » pour ce prêt sur cette garantie. Concrètement, il
  s'agit d'un pourcentage indiquant quelle proportion du capital restant dû du
  prêt sera pris en charge par l'assurance en cas de sinistre
- ``start_date`` : Les quotités peuvent évoluer dans le temps, il est donc
  nécessaire de conserver et de versionner l'information du pourcentage
  concerné

Données de tarification
-----------------------

Le contrat porte également des informations techniques, calculées
automatiquement, et nécessaires notamment pour la génération automatique des
factures. Lors de l'activation du contrat, ainsi que de l'application de la
majorité des avenants, ces informations sont recalculées de sorte que l'on soit
en mesure de correctement générer les nouvelles quittances.

Ces informations sont portées par le modèle ``contract.premium``. Ce modèle
contient les informations suivantes :

- ``amount`` + ``frequency`` : permettent de définir un « Tarif ». On parle de
  stocker une information du type « 10 € par mois » ou « 150 € par an »
- ``account`` : le compte comptable qui sera utilisé lors de la facturation.
  Sera peut-être remplacé par un champ fonction à terme
- ``start`` et ``end`` : la période pendant laquelle ce tarif est valide.
  Typiquement, les champs ``start`` seront renseignés à la création de la
  premium, et le champ ``end`` sera mis à jour en cas de modification du
  contrat impliquant un recalcul des tarifs
- ``rated_entity`` : un lien vers l'objet de paramétrage ayant servi au calcul
  de la ligne de tarif. Dans la grande majorité des cas, il s'agira d'une
  ``offered.option.description``, et quelques fois d'un ``account.fee``
- ``loan`` : dans le cas où la ligne de prime porte sur une garantie
  emprunteur, chaque prêt donnera lieu à des primes différentes. Ce champ
  permet de les identifier

Les autres champs (``contract``, ``covered_element``, ``option``, ``fee`` et
``extra_premium``) servent à stocker le « bout » du contrat ayant servi de base
au calcul. Concrètement, les champs véritablement utilisés sont ``option``, et
parfois ``fee`` et ``extra_premium``. Il est possible que cela évolue dans le
futur.

Lors de la génération des quittances, ces données sont utilisées pour calculer
le contenu de la facture (les différentes ``account.invoice.line``). Le détail
de ce calcul est expliqué plus en détail dans la documentation sur le
paramétrage de **Coog**.

Autres
------

Statut du contrat
~~~~~~~~~~~~~~~~~

Les contrats disposent des champs ``status`` et ``sub_status``. Ces champs sont
à la fois très importants, et difficiles à utiliser

Le champ ``status`` peut avoir les valeurs suivantes :

- ``quote`` : le contrat est un devis. Il s'agit du seul statut où tout est
  modifiable, il n'a a priori pas encore de valeur légale
- ``active`` : le contrat  est actif
- ``terminated`` : le contrat est résilié, et la date de résiliation est passée
- ``void`` : le contrat n'a pas d'existence légale. Il y a deux cas principaux
  pour cette valeur : la « renonciation », où le souscripteur informe
  l'assureur dans un délai légal son souhaite de renoncer au contrat, ou bien
  toutes les possibles erreurs de gestion ayant entraîné l'activation du
  contrat alors que cela n'aurait pas du être fait
- ``declined`` : statut dans lequel se retrouve un devis (``quote``) n'ayant
  jamais été activé. Il est également possible de supprimer le devis de la base
  de données
- ``hold`` : le contrat est « suspendu ». Le cas classique correspond aux
  contrats non payés, qui sont en général automatiquement suspendus au bout
  d'un certain temps. Les contrats peuvent également être suspendu
  manuellement, par exemple si les gestionnaires on connaissance du décès du
  souscripteur

Le champ ``sub_status`` permet d'affiner l'information technique du ``status``
en ajoutant un contexte fonctionnel (le contrat est suspendu « pour impayé »,
il est résilié « suite à demande du souscripteur », etc.)

Ce qu'il est indispensable de noter est que les statuts *Actif* et *Résilié*
**ne suffisent pas à eux seuls pour déterminer la validité du contrat**.
Autrement dit, ces champs sont censés être à jour, mais la vraie information
est stockée dans les dates de début et de fin du contrat (dans
``contract.activation_history``).

Si à un moment on a besoin de vérifier si le contrat est actif, la bonne façon
est de vérifier par rapport aux dates, en plus du statut.
