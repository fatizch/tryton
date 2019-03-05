L'assurance
===========

L'objet ici est de donner une première vision globale du métier de l'assurance
et des différents éléments gérés par **Coog**.

Le document sépare les aspects fonctionnels des aspects techniques. Pour les
entités de paramétrage, se référer à la section *Formation administration* de
la documentation.

Principe de l'assurance
-----------------------

Formellement, l'assurance consiste à limiter le coût d'un évènement aléatoire
en mutualisant ce coût pour les personnes exposées à cet évènement.

Concrètement, moyennant le paiement d'une cotisation régulière, l'assureur (ou
la mutuelle) s'engage à payer des indemnités correspondants aux pertes
engendrées par un événement.

Exemple :

Dans le cas d'une assurance automobile, typiquement pour le vol. Le
souscripteur du contrat paye par exemple 10 € par mois. Dans le cas où sa
voiture est volée, l'assureur lui paye la valeur de sa voiture en compensation.

La logique sous-jacente est que si, en moyenne, une personne a une chance sur
100 de se faire voler sa voiture dans l'année et que la moyenne des valeurs des
voitures est de 12 000 €, l'argent qui sera payé par l'assureur par 100
personnes (10 € * 12 * 100) sera égal à la valeur de la voiture à rembourser.

L'assureur va en général faire payer un peu plus cher que le nécessaire pour
payer ses salariés, etc., mais la logique est celle-là.

Dans ce processus, **Coog**, en tant que logiciel de *Gestion*, est en charge
de tout ou partie des éléments suivants :

- Stockage des informations sur les contrats (quelles personnes ont signées
  pour quelles garanties). Dans notre exemple, le contrat contient notamment
  les informations d'identification du souscripteur, les informations de la
  voiture « couverte » par le contrat, etc.
- Stockage des informations sur les sinistres (quels sont les événements ayant
  donné lieu à des remboursements). Ici, le fait qu'à une certaine date, la
  voiture de M. X ait été volée, et qu'à ce titre on lui ai fait un versement
  de 12 000 €
- Calcul et prélèvement des cotisations (les 10 € par mois) pour tous les
  contrats enregistrés dans le système, ainsi que versement des remboursements
  correspondants aux sinistres ayant survenu

Il ne s'agit que d'une vision partielle de ce que fait concrètement **Coog**,
mais elle suffira dans un premier temps. On peut globalement retenir que
**Coog** permet de gérer les trois grands « domaines fonctionnels » suivants,
que nous allons détailler par la suite :

- Contrats
- Sinistres
- Comptabilité associée

Lignes métiers
--------------

Les métiers de l'assurance sont organisés autour de « lignes métier ». On
pourrait également parler de *catégories* d'assurances.

**Coog** a pour ambition, à terme, de permettre de gérer toutes ces lignes
métiers, et le modèle technique a été conçu pour permettre de le faire.
Ci-dessous une présentation rapide de ces lignes métiers, avec quelques-unes de
leurs spécificités.

Prévoyance
~~~~~~~~~~

L'assurance *Prévoyance* a pour objet la compensation financières de problèmes
de santé. Concrètement, les « assurés » d'un contrat *Prévoyance* sont des
personnes physiques, et les événements couverts par l'assurance seront
typiquement :

- La maladie (on parle d'« Interruption Temporaire de Travail » ou *ITT*).
  L'assurance a pour but de se substituer au salaire non perçu du fait de
  l'absence du salarié à son travail. Concrètement, dans le cas d'arrêts
  maladie de (relativement) longue durée, les indemnisations de la sécurité
  sociale ne compensent pas forcément la totalité du salaire « normal ».
  L'assurance vient alors en complément, pour maintenir (totalement ou
  partiellement) le salaire effectivement perçu à la fin du mois
- L'invalidité. En cas d'accident grave, ou de complications suite à une
  maladie, une personne peut devenir « invalide » au sens légal du terme. Dans
  ce cas, l'assurance propose en général une rente permettant de compléter les
  revenus potentiellement diminués du fait de l'invalidité
- Le décès de l'assuré. Il y a plusieurs possibilités en général pour les
  indemnisations proposées par l'assurance en cas de décès, l'objet étant de
  faciliter la vie de sa famille. On retrouve souvent un ou plusieurs des
  éléments suivants :

  * Un capital versé en une seule fois
  * Une rente pour le conjoint survivant (principalement dans le cas où les
    revenus étaient très différents)
  * Une rente pour l'éducation des enfants

Il ne s'agit que d'une description des cas « classiques » de la prévoyance, il
en existe plein de variantes différentes.

Emprunteur
~~~~~~~~~~

L'assurance *Emprunteur* est une variante de l'assurance *Prévoyance* utilisée
lors de la souscription de prêts. L'objet de cette assurance est de rembourser
à la banque le capital restant dû d'un prêt suite à un accident survenu à
la personne ayant souscrit l'emprunt.

En France, cette assurance est systématiquement demandée pour la garantie
« Décès ». Autrement dit, la banque veut être certaine que si l'emprunteur
décède, elle soit remboursée du montant restant du prêt.

La grande différence avec l'assurance *Prévoyance* est que le montant
« couvert » (autrement dit qui sera remboursé) est automatiquement calculé à
partir des caractéristiques du ou des prêts adossés au contrat. Par ailleurs,
contrairement à la *Prévoyance* où les bénéficiaires attendus sont les membres
de la famille, ici le bénéficiaire final sera la banque auprès de laquelle le
prêt a été contracté.

Les garanties classiques seront :

- Décès / Perte Totale et Irréversible d'Autonomie (PTIA) : Remboursement à la
  banque du capital restant dû sur le prêt au moment de l'événement
- Interruption Temporaire de Travail : Remboursement de tout ou partie des
  échéances du prêt pendant la durée de l'interruption
- Chomage : Prise en charge par l'assureur des échéances du prêt pendant une
  période de recherche d'emploi

Santé
~~~~~

La *Santé* est un secteur particulier de l'assurance visant à couvrir les frais
médicaux liés à une maladie (par exemple). La différence avec la *Préovyance*
est la suivante :

- En *Prévoyance*, on cherche à compenser les conséquences d'un accident (le
  fait que l'on ne peut plus travailler typiquement)
- En *Santé*, on se concentre sur le paiement des frais médicaux.
  Consultations, médicaments, hospitalisation, etc.

En France, on parle souvent de *complémentaire Santé*, dans le sens où
l'assurance a vocation à prendre en charge tout ou partie de ce que la
*Sécurité Sociale* ne rembourse pas.

Concrètement, en cas de consultation chez un médecin facturée 50 €, la sécurité
sociale remboursera typiquement 20 €, et l'assurance prendra à sa charge le
reste, ou uniquement une partie en fonction des caractéristiques du contrat.

Automobile
~~~~~~~~~~

TODO : Pas encore dans Coog

Multi-Risque Habitation
~~~~~~~~~~~~~~~~~~~~~~~

TODO : Pas encore dans Coog

Contrat
-------

Le contrat est l'élément de base de l'assurance. Il s'agit d'un document signé
par les deux parties (le souscripteur du contrat, et l'assureur), qui détaille
les engagements de chacun.

**Coog** doit stocker toutes ces données (au delà du contrat « physique ») dans
une base de données, afin de pouvoir *gérer* le contrat.

Ces données incluent notamment :

- Le souscripteur du contrat
- Le produit souscrit
- La date de prise d'effet / date de fin
- Les risques assurés
- Les garanties souscrites sur ces risques
- Les information de facturation

Souscripteur
~~~~~~~~~~~~

Le *Souscripteur* est la personne ayant signé le contrat. Attention, on parle
par défaut de « personne », mais il peut s'agir d'une personne *physique* (i.e.
un humain) comme d'une personne *morale* (société, association, etc.)

Les informations classiques que l'on retrouvera sur le souscripteur seront :

- Son nom / prénom
- Une ou des adresses
- Un ou des comptes bancaires, éventuellement partagés avec d'autres (cas des
  comptes joins entre époux)
- D'autres informations dépendant du type d'assurance concerné (date de
  naissance, numéro de sécurité sociale, etc.)

Produit
~~~~~~~

Le *Produit* correspond à la description des caractéristiques « standard » du
contrat. Il va concrètement contenir toutes les informations écrites dans les
documents qui sont signés lors de la souscription.

Dans **Coog**, le produit contient des éléments de configuration qui sont
ensuite utilisés lors des différents traitements auomatiques. On va y retrouver
typiquement :

- Les modèles de document à utiliser pour les contrats
- Les différentes garanties disponibles à la souscription
- Le type métier du produit (s'agit-il d'assurance automobile, prévoyance,
  santé, etc.)
- L'assureur
- etc.

Dates de début / fin
~~~~~~~~~~~~~~~~~~~~

Les contrats d'assurance sont valides sur une période donnée. Cette période
correspond aux dates pendant lesquelles :

- Le souscripteur s'engage à payer ses cotisations
- L'assureur s'engage à payer les sinistres

Il y a concrètement trois familles de contrats d'assurance (l'appartenance à
ces familles dépendant du produit souscrit) :

- Les contrats « one-shot », dont les dates de début et de fin sont connues dès
  la souscription et ne seront a priori plus modifiés (exemple : assurance
  emprunteur, où la durée du contrat est liée à la durée des prêts assurés)
- Les contrats « renouvelables ». Ces contrats ont des dates de début et de fin
  connues à la souscription (typiquement pour une durée d'un an), mais sont par
  défaut « renouvelés » une fois la date de fin attente. Le renouvellement
  consiste en la réactivation du contrat pour une nouvelle période (exemple :
  contrats d'assurance habitation)
- Les contrats « viagers », où la date de fin n'est pas connue à l'avance. Il
  s'agit en général de contrats conçus pour s'arrêter au décès de l'assuré
  (exemple : contrats d'épargne)

Risques assurés
~~~~~~~~~~~~~~~

L'objet du contrat d'assurance est de couvrir un risque. Ce risque peut
porter :

- Sur des objets physiques (véhicules, habitations, etc.), pour lesquels
  l'assurance consistera sur des risques de vols / dégradations / etc.
- Sur des personnes physiques (on parle alors d'« assurés ») pour lesquels
  seront assurés les « événements imprévus de la vie ». Il s'agit concrètement
  des risques de maladie / invalidité / décès

**Coog** introduit une forte distinction entre la notion de « risque assuré »
(ou « risque couvert ») et les garanties couvrant se risque. Concrètement, on
peut voir le *risque* comme étant l'objet de l'événement couvert par
l'assurance.

Garanties
~~~~~~~~~

Les *garanties* sur un contrat correspondent à l'engagement de l'assureur à
indemniser le souscripteur dans le cas où certains événements arrivent sur un
*risque*.

Il peut y avoir plusieurs garanties rattachées à un *risque* donné. Par
exemple, en assurance prévoyance, une personne donnée peut être couverte par
plusieurs garanties, qui « couvrent » des événements différents :

- Risque de décès : en cas de décès, l'assureur s'engage à verser une rente aux
  enfants de l'assurés, et / ou un capital à son conjoint
- Risque de maladie : en cas d'arrêt de travail, l'assureur complètera les
  indemnités versées par la sécurité sociale afin qu'il n'y ai pas (ou peu) de
  baisse de revenues
- Risque d'invalidité : en cas d'accident grave donnant lieu à une invalidité,
  l'assuré aura droit à une rente à vie pour compenser les pertes de revenus
  liés à cette invalidité

Chacune de ces garanties est décrite quelque part dans le paramétrage de
**Coog**, et peut proposer des choix multiples lors de la souscription (par
exemple, dans le cas du risque de maladie, le montant qui sera payé chaque jour
par l'assureur à l'assuré).

Éléments de facturation
~~~~~~~~~~~~~~~~~~~~~~~

La souscription d'un contrat implique le règlement de « cotisations » par le
souscripteur à l'assureur. Concrètement, le fonctionnement habituel est qu'au
moment de la souscription, le souscripteur signe un document autorisant
l'assureur à prélever tous les mois sur son compte bancaire le montant de la
cotisation.

Dans les faits, on stocke entre autres sur le contrat les informations
suivantes :

- Mode de paiement : contient notamment la fréquence des paiements. En fonction
  de la configuration, peut également permettre de choisir si les paiements
  sont fait via des prélèvements automatiques, ou manuellement via l'envoi de
  chèques
- Compte bancaire à utiliser lors des prélèvements

Sinistres
---------

L'autre élément central de l'assurance, après le *Contrat*, est le *Sinistre*.
Le contrat a pour but de décrire les conditions dans lesquelles un *Sinistre*
sera traité à partir du moment où il est déclaré.

Concrètement, le contrat définit le cadre dans lequel les sinistres seront pris
en charge par l'assureur.

Un sinistre est fondamentalement lié à un ou plusieurs *Évenements*. Chacun de
ces *Événements* peut donner lieu aux versements d'*Indemnisations* liées aux
*Prestations* auxquelles les contrats souscrits donnent droit.

Événement
~~~~~~~~~

L'élément « de base » d'un sinistre est l'*Événement*. Concrètement, il s'agit
de la description de ce qui est arrivé, et qui doit donner lieu à une
indemnisation.

Par exemple, dans le cas d'un arrêt de travail, on y retrouvera typiquement les
informations suivantes :

- Type de « Préjudice » (la catégorie d'assurance mise en oeuvre). C'est à cet
  endroit que l'on indiquera « Arrêt de travail » dans notre exemple
- Date de début de l'arrêt de travail
- Date de fin / motif de fin si applicable
- « Fait générateur » : dans certains cas, on souhaite avoir des précisions sur
  les conditions dans lesquelles l'événement s'est produit. S'agissait-il d'un
  accident, d'une maladie, d'une grossesse, etc. Cette information est parfois
  indispensable pour déterminer si des indemnisations seront versées (par
  exemple, vous ne serez pas couvert pour un suicide dans la première année du
  contrat)
- Personne assurée (dans le cas d'assurances prévoyance ou santé), sinon
  l'objet couvert (voiture, adresse, etc.)

L'événement est le point de départ du traitement du dossier de sinistre. À
noter qu'un dossier peut être composé de plusieurs événements. Par exemple,
dans le cas d'un arrêt de travail, il est possible (si malheureusement la
maladie est grave) que l'assuré décède par la suite. Dans ce cas, en général,
la gestion des indemnisations pour la partie Décès sera gérée dans le même
dossier que la partie Arrêt de travail, mais dans un événement différent.

Prestation
~~~~~~~~~~

Chaque *Événement* peut donner droit à plusieurs *Prestations*. L'événement est
une description concrète de **faits réels**. Il permet de stocker dans le
système les caractéristiques du préjudice subi par l'assuré.

Les *Prestations*, quant à elles, représentent les « droits » de l'assuré.
Concrètement, une fois les données de l'événement saisies (notamment qui est
concerné, ainsi que la date de survenance), **Coog** va rechercher sur tous les
contrats ceux pour lesquels l'assuré avait des garanties actives à la date de
l'événément. Il va ensuite filtrer pour ces garanties les prestations
configurées compatibles avec le type et les caractéristiques de l'événement
déclaré.

Dis autrement, il va vérifier dans les « petites lignes » du contrat si la
personne est bien couverte pour ce qui lui est arrivée.

Ensuite, il va créer chaque prestation possible, en la rattachant à
l'événement. Il peut y avoir **plusieurs prestations** pour un événement donné
(par exemple, dans le cas d'un Décès, on peut avoir une prestation de versement
de capital, ainsi qu'une rente éducation pour les enfants).

Indemnisation
~~~~~~~~~~~~~

Une fois les *Prestations* identifiées et validées (il peut être nécessaire de
demander des documents justificatifs, par exemple un acte de décès),
l'utilisateur de l'application va pouvoir déclencher le paiement
d'*Indemnisations* au bénéficiaire du contrat (le souscripteur en général, sauf
en cas de décès où en général les bénéficiaires sont déterminés lors de la
souscription).

Il y a plusieurs grandes familles de prestations :

- Capital : Un montant pré-determiné est versé en une seule fois lors du
  traitement de la prestation
- Rente : Tous les mois / trimestres, le bénéficiaire reçoit un versement d'une
  somme convenue lors de la souscription, éventuellement revalorisée au fil des
  ans
- Indemnité journalières : Le bénéficiaire est indemnisé au jour le jour (ou
  par groupes de jours) en fonction des justificatifs envoyés. Il s'agit du cas
  classiquement associé aux arrêts de travail, où le versement des
  indemnisations est conditionné à la réception des justificatifs de règlements
  de la sécurité sociale

Comptabilité
------------

TODO
