Généralités
===========

Cette section regroupe quelques « trucs » à savoir sur la façon dont est
développée **Coog**. Certaines informations se trouvent également dans le
*Glossaire*.

Versionning
-----------

Plusieurs modèles ont un modèle séparé dédié à stocker des informations
susceptibles d'évoluer au cours du temps (ex : le modèle
``contract.extra_data`` stocke les informations versionnées pour les contrats).

Il y a deux approches pour gérer les dates de validité de ces modèles :

- Un seul champ ``date`` permet d'ordonner les différents éléments
- Deux champs, ``start_date`` / ``end_date`` (ou juste ``start`` / ``end``)

La première approche permet d'assurer une continuité (on est certain qu'il n'y
a pas de « trous », étant donné que les dates de fin sont implicites. Il s'agit
en général de modèles permettant de garder des changements d'information.

La seconde est plus explicite, mais peut donner lieu à des problèmes lors des
traitements automatiques. Par exemple, un client peut avoir plusieurs adresses
valides à une date donnée, mais également aucune (dans le cas où d'erreurs de
saisies, ou cas extrêmes où il n'a effectivement aucune adresse). Dans ce cas,
l'approche « implicite » avec un seul champ ``date`` ne permet pas de
correctement enregistrer l'information.

De façon générale, les champs de date utilisent l'approche suivante :

- Une ``date`` (ou ``start_date`` / ``start``) vide correspond au minimum de
  date valide pour le champ concerné. Par exemple, pour un objet versionné tel
  que ``contract.extra_data``, il s'agira de la date d'effet initiale du
  contrat correspondant
- Une ``end_date`` (ou ``end``) vide à la date maximum correspondant

Pour les cas où l'objet rattaché n'a pas de dates « limites » évidentes (par
exemple sur les dates de validité d'une adresse), des valeurs vides
correspondent à ``datetime.date.min`` et ``datetime.date.max``.

Cette approche n'est pas complètement uniforme (dans le sens où pour certains
cas les valeurs doivent être explicitées), mais est préférable pour les
nouveaux dévelopements. L'idée générale est que cela permet d'éviter d'avoir à
mettre à jour les dates des « sous-objets » si on modifie la date de l'objet
maître.

Demandes de documents
---------------------

Un besoin récurrent lors de la gestion d'assurance est de demander des
documents avant de pouvoir valider certaines actions. Par exemple, il ne sera
en général pas possible d'activer un contrat si l'on n'a pas reçu le *Bulletin
d'adhésion* (le document signé du sosucripteur demandant la souscription), ou
bien un *Mandat SEPA* s'il souhaite payer par prélèvement automatique.

Le modèle permettant de stocker cette information est
``document.request.line``. Il s'agit d'un modèle destiné à être rattaché via un
``One2Many`` sur le modèle « parent » (contrat, sinistre, etc.), qui utilise un
champ ``Reference`` en lien inverse.

Il contient notamment les informations suivantes :

- ``document_desc`` : un lien vers un ``document.description``, qui est un
  élément de paramétrage représentant un « type » métier de document (les
  fameux « bulletin d'adhésion » ou « mandat SEPA »
- ``for_object`` : la référence vers l'objet pour lequel le document est
  demandé
- ``blocking`` : un booléen permettant de savoir si le document est bloquant ou
  pas pour les processus métiers rattachés au modèle parent

Batchs
------

**Coog** a pour objet d'automatiser le maximum de choses lors de la gestion des
contrats / sinistres. Pour ce faire, de nombreux traitements sont effectués
automatiquement le soir, lors de traitements « batchs ».

Fonctionnement des batchs
~~~~~~~~~~~~~~~~~~~~~~~~~

**Coog** utilise la librairie ``celery`` pour les traitements batch.
Concrètement, en plus du serveur applicatif, on trouve des « workers batchs »,
lancés (en environnement de développement) à l'aide de la commande :

.. code:: bash

   coog celery start N

avec ``N`` le nombre de workers à démarrer.

Une fois les workers démarrés, lancer un batch se fait à l'aide de la
commande :

.. code:: bash

   coog batch exec nom.du.batch --param1=... --param2=...

Techniquement, cette commande va alimenter une liste de tâches à traiter, puis
attendre que les workers celery, qui sont également connectés à cette liste de
tâches, aient fini de les traiter.

Implémentation
~~~~~~~~~~~~~~

Toutes les classes de batch héritent de la classe
``coog_core.batch.BatchRoot``. Les deux méthodes importantes de cette classe
(celles qui seront surchargée lors de l'implémentation d'un batch) sont :

- ``select_ids``
- ``execute``

``select_ids`` correspond à la recherche des tâches à traiter, et ``execute``
au traitement à appliquer à une tâche donnée.

:Note: Pour les cas simples, on peut éviter d'écrire la requête dans
       ``select_ids`` et se contenter de surcharger les méthodes
       ``get_batch_domain`` et ``get_batch_search_model``

De façon générale, ``select_ids`` effectuera une recherche dans le base de
données, sur la base des arguments en paramètres. Le résultat de cette requête
sera ensuite découpés en tâches selon le paramétrage du batch (une seule tâche,
des groupes de 10, etc.)

L'exécution de ces tâches consiste alors en l'appel de la méthode ``execute``,
qui prend dans le paramètre ``ids`` la liste des ``id`` des objets à traiter,
dans ``objects`` les objets correspondants (si ``get_batch_main_model_name``
est renseigné), ainsi que les paramètres supplémentaires passés au batch.

Chaînes
~~~~~~~

Certains traitements « métiers » nécessitent plusieurs traitements techniques
pour être effectués.

Par exemple, lors du quittancement des contrats (création des quittances pour
un nouveau mois), la génération se fait en trois étapes :

- Création des quittances
- Numérotation
- Émission (comptabilisation)

L'intérêt de l'approche de **Coog** pour les traitements batchs est de
permettre au maximum la parallélisation des traitements (afin de pouvoir scaler
horizontalement). Ici toutefois, le second traitement (la numérotation) n'est
pas parallélisatble pour des raisons métier, et a donc nécessité de découpé le
traitement en trois.

La notion de chaîne permet d'ajouter un niveau d'abstraction pour le lancement
des batchs. Pour le cas ci-dessous, la chaîne peut être lancée simplement via
la commande :

.. code:: bash

   coog chain -- contract_insurance_invoice invoice --treatment-date=XXXX-XX-XX

Cette commande va « s'occuper » de lancer les trois batchs les uns à la suite
des autres, ne lançant le suivant que lorsque le traitement précédent s'est
achevé. Les paramètres seront également passés aux différents traitements qui
en ont besoin.

De façon générale, lors de l'écriture d'un nouveau batch, il est demandé :

- ou bien de l'intégrer à une chaîne existante
- ou bien de créer une nouvelle chaîne qui lui est dédiée

Les fichiers décrivant les chaînes d'un module se trouvent dans le répertoire
``chain`` du module (s'il existe).

Exemples
~~~~~~~~

Quelques exemples de batch pour « apprendre » à s'en servir :

- Dans le module ``coog_core``, le batch ``ir.ui.view`` est un batch souvent
  utilisé en tests (il n'a pas de réel sens métier). Il s'agit d'un batch où le
  ``select_ids`` n'est pas directement implémenté, mais construit
  automatiquement à partir du domaine définit dans les méthodes
- Dans le module ``contract_insurance_invoice`` se trouve la chaîne de batchs
  de quittancement, qui est l'une des plus importantes. Les ``select_ids``
  devant être enrichis dans d'autres modules, la construction de la requête est
  découpée en plusieurs méthodes, mais le fonctionnement final est le même

Moteur de règles
----------------

Le fonctionnement de **Coog** dépend fortement de l'utilisation du *Moteur de
règle* (``rule_engine``).

En général, les règles sont « choisies » dans des objets de paramétrage
(produits, garanties offertes, etc.), et utilisées lors de traitements métier
sur des données de gestion (contrats, etc.)

Étant donné les différentes possibilités offertes par les règles, l'ajout d'un
champ « règle » (un Many2One vers un ``rule_engine``) se fait via l'utilisation
de la méthode ``get_rule_mixin`` du module ``rule_engine``. L'utilisation de
cette méthode permet de s'assurer que les différents champs liés à cette règle
sont bien créés et mis à jour automatiquement.

Lors de l'appel d'une règle dans le code, il est nécessaire d'auparavant
construire un contexte d'exécution :

.. code:: python

   context = {}
   self.init_dict_for_rule_engine(context)
   my_rule.execute(context, parameters=rule_parameters)

Le contexte contient les informations qui vont permettre à la règle d'évaluer
les données métiers utilisées, les ``rule_parameters`` correspondent aux
*Paramètres de règles* utilisés s'ils sont renseignés à ce moment.

L'appel à la méthode ``execute`` des règles retourne une instance de la classe
``RuleEngineResult``, qui contient outre le résultats les différents messages
qui ont été ajoutés « fonctionnellement » lors de l'exécution.
