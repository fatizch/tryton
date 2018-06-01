Architecture de Coog
====================

Philosophie
-----------

**Coog** fonctionne selon une approche modulaire. Les différents domaines
fonctionnels sont ainsi installables à la demande. Cela permet de limiter la
pollution d'une installation avec des points d'entrées et comportements non
indispensables. L'intérêt est, par exemple, de ne pas avoir la complexité de la
configuration des contrats collectifs pour une installation où ce besoin n'est
pas présent.

Modules haut niveau
-------------------

Suivant cette logique, **Coog** est composé de plus de 200 modules. Certains
sont « indispensables » et seront présents dans toutes les installations
(gestion des tiers, comptabilité, etc.), d'autres répondent à des besoins
très précis et ne seront installés que rarement (envoi de SMS via la plateforme
Primotexto par exemple).

Afin de donner une idée plus claire des fonctionnalités disponibles, et donc
nécessitant une configuration, voici dans les grandes lignes les modules « haut
niveau » de **Coog**, et le périmètre qu'ils couvrent :

Gestion des tiers
~~~~~~~~~~~~~~~~~

Cette partie sera installée dans 100% des cas, et concerne tout ce qui est lié
à la saisie des différents acteurs utilisés dans l'application. Cela inclut :

* Les personnes physiques / morales souscriptrices
* Les courtiers
* Les assureurs
* Les organismes bancaires
* etc.

Gestion des contrats
~~~~~~~~~~~~~~~~~~~~

Également, les contrats seront systématiquements présents dans **Coog**. En
fonction des besoins, seules certaines parties seront nécessaires. Par exemple,
il n'est pas forcément indispensable de pouvoir saisir les contrats directement
via l'application, ils peuvent être importés via une plateforme de souscription
externe

Comptabilité
~~~~~~~~~~~~

**Coog** s'appuie sur des bases comptables très fortes. Autrement dit, toutes
les opérations impliquant des transferts d'argent (quittancement des contrats,
règlement des sinistres, gestion des commissions, etc.) nécessitent des
opérations comptables. Nous nous appliquerons dans le cadre de cette formation
à correctement expliquer les implications comptables des différentes actions
disponibles dans l'application

Gestion des sinistres
~~~~~~~~~~~~~~~~~~~~~

La gestion des sinistres dans **Coog** dépend fortement (et logiquement) des
modules de gestion des contrats, ainsi que de la comptabilité afin de permettre
les décaissements

Commissionnement
~~~~~~~~~~~~~~~~

Les modules de commissionnement permettent de paramétrer tout ce qui touche à
la rémunération des acteurs concernés par un contrat :

* Apporteur d'affaire
* Sur-apporteur
* Assureur

Ils assurent également la gestion des réseaux de distribution, et la hiérarchie
entre les différentes entités

Modules techniques
~~~~~~~~~~~~~~~~~~

**Coog** s'appuie sur un certain nombre de modules techniques qui lui confèrent
sa flexibilité. La plupart seront abordés dans le cadre de cette formation :

* Moteur de règles
* Moteur d'événements
* Éditique
* Gestion des droits

Lignes métier
~~~~~~~~~~~~~

Les différentes lignes métier n'apparaissent pas ici, car elles sont davantage
des extensions des modules haut niveau que des modifications profondes du
fonctionnement sous-jacent de **Coog**. Par exemple, un contrat emprunteur est
certes très différent par bien des aspects d'un contrat IARD, mais en
termes de paramétrage la principale différence se retrouve dans les algorithmes
et le nom des données utilisées dans les différentes règles de calcul.

Principe d'accès limité
-----------------------

Un certain nombre de paramétrages (en particulier pour la gestion des
habilitations) dans **Coog** fonctionne selon un principe d'« accès limité ».
Le principe est simple :

* Si personne n'a explicitement l'accès, tout le monde l'a
* À partir du moment où quelqu'un acquiert explicitement cet accès, les autres
  le perdent

Il est indispensable de comprendre ce fonctionnement, afin d'éviter les
incompréhensions lors du paramétrage. Concrètement, cela signifie :

* Qu'il est relativement simple de faire un nouveau paramétrage global. Par
  exemple, si l'on créé un nouveau modèle de courrier sans le rattacher
  explicitement à un produit, il est automatiquement disponible sur tous les
  produits
* À l'inverse, il est relativement fastidieux de travailler avec des
  exceptions. Si l'on souhaite que ce même modèle de courrier soit disponible
  sur tous les produits sauf un, il va falloir le rattacher à tous les produits
  un par un, à l'exception de celui à exclure
