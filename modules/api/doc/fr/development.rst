Déclaration de l'API
~~~~~~~~~~~~~~~~~~~~

Une dépendance au module "api" doit être déclarée dans le champ "extras_depends"
du fichier tryton.cfg du  module pour lequel l'API est développée.

.. code:: python

    extras_depend: api

La déclaration du modèle dans le fichier "__init__.py" du module sera également
un peu différente pour signifier la dépendance au module "api" seulement dans le
cas ou ce dernier est installé.

.. code:: python

    Pool.register( api.APIParty, module='bank_fr', type_='model',
        depends=['api'])

Le module sera alors chargé après le module API si ce dernier est activé. Dans
ce cas là, la classe modélisant l'API sera enregistrée dans le Pool.

Un modèle d'API métier doit hériter d'APIMixin et ne devrait pas hériter de
ModelSQL ou ModelView. Chaque namespace (ex. party, accounting...) n'aura qu'un
seul modèle d'API.

Les exemples suivants sont pour la plupart tirés de ``bank_fr/api.py``.

Définition des méthodes
~~~~~~~~~~~~~~~~~~~~~~~

Les APIs seront définies par des méthodes de classe comportant un argument pour
les informations reçues en entrée :

.. code:: python

    @classmethod def bank_from_number(cls, parameters):
        data = getData(parameters['number'])
        # ...
        return data

Elles sont déclarées dans le champ _apis du modèle dans lequel elles sont
définies, où l'on peut également les paramétrer.

.. code:: python

    @classmethod def __setup__(cls):
        super().__setup__() cls._apis.update({
                'bank_from_number': {
                    'description': 'Extracts the bank information from the '\
                        'account number',
                    'readonly': True,
                    'public': True,
                    }
                })

L'option facultative 'public' indique si des contrôles d'accès seront appliqués
lors d'un appel à l'API.

Éventuellement, ce contrôle d'accès peut être personalisé en overridant la
méthode _check_access (avec précaution).

.. code:: python

    @classmethod def _check_access(cls, api_name, parameters):
        # ...
        Pool().get('api').check_access(cls, api_name)

Définition et validation des entrées et sorties
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Le schéma d'entrée de l'API au format `JSON-Schema<https://json-schema.org/>_`
sera défini dans une méthode ``_<nom_de_l_api>_schema``.  Il sera utilisé pour
vérifier les entrées.

.. code:: python

    @classmethod def _bank_from_number_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {'number': {'type': 'string'}},
            'required': ['number'],
            }

Le schéma de sortie pourra être renseigné dans une méthode
``_<nom_de_l_api>_output_schema`` pour donner une idée du format des résultats
renvoyés.

.. code:: python

    @classmethod def _bank_from_number_output_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'id': OBJECT_ID_SCHEMA,
                'name': {'type': 'string'},
                'bic': {'type': 'string'},
                },
            }

La validation de la sortie ne sera pas faite par défaut pour des raisons de
performances. Néanmoins en mode debug des warnings pourront être soulevés.

La conversion des paramètres d'entrée dans le type voulu auront lieu dans une
méthode ``_<nom_de_l_api>_convert_input``.

.. code:: python

    @classmethod def _my_api_convert_input(cls, parameters):
        parameters['price'] = Decimal(parameters['price'])
        return parameters

Après la conversion des paramètres d'entrée, une validation peut être effectuée
si la définition JSON Schema n'est pas suffisante.

.. code:: python

    @classmethod def _my_api_validate_input(cls, parameters):
        if parameters['count'] < 0:
            return [{
                'type': 'validation',
                'data': {
                    'name': 'invalid_count',
                    'description': 'Count should be positive',
                    },
                }]

Des exemples d'utilisation de l'API peut être fournis dans
``_<nom_de_l_api>_examples`` :

.. code:: python

    @classmethod def _bank_from_number_examples(cls):
        return [{
            'input': {'number': '123425425'},
            'output': {
                'id': 1,
                'name': 'Ma banque',
                'bic': 'XXXXXXXXXX',
                },
            }]

À moins que le flag ``disable_schema_tests`` ne soit explicitement activé, leur
format sera validé avec les schémas déclarés précédement.  Ce comportement est à
éviter à moins que des incompatibilités existent entre des modules à cause de
dépendances non déclarées par exemple. Le flag sera de toute façon ignoré par
les tests unitaires.

Ajout d'une API dans portal
~~~~~~~~~~~~~~~~~~~~~~~~~~~

L'ajout d'une API dans coog-portal se fait dans
*coog-portal/packages/coog-api/src/modules* soit en ajoutant un nouveau module
soit en étendant un module existant. Un module se compose des fichiers
suivants:

 - **api.controller.js** : permet de spécifier le type de requête, le chemin
   d'accès, le code de retour ainsi que la fonction provenant du middleware
   permettant de traiter la requête.

 - **api.coog.js** : permet d'appeler la méthode tryton correspondant au
   traitement des données.

 - **api.middleware.js** : permet de décrire le traitement de la requête et de
   retourner le résultat ou les erreurs.

 - **api.module.js** : description de l'architecture du module.

Lors de la création d'un nouveau module il ne faut pas oublier de mettre à jour
le fichier *coog-portal/packages/coog-api/src/index.js* en y ajoutant le chemin
vers le fichier module ainsi que le chemin d'accès aux requêtes de ce module.

Des exemples simples peuvent être trouvés dans:
*coog-portal/packages/coog-api/src/modules/broker/*

Mise à jour de la documentation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

La documentation se situe dans *coog-portal/packages/coog-api/src/doc* et est un
fichier .yaml. La documentation contient le chemin de la requête, une description
de ce qu'elle fait, le contenu de la requête ainsi que les différentes réponses
possibles. Il est possible d'accéder à la documentation, lorsque la gateway est
lancée, dans un navigateur à l'adresse suivante:
*http://localhost:<gateway-port>/doc*

Appel d'une API par JSON-RPC
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pour tester l'API on peut utiliser la bibliothèque Proteus pour intéragir avec
le serveur Coog depuis un script de la manière dont le client le ferait.

.. code:: python

    from proteus import config, set_xmlrpc

    # Format: http://<login>:<password>@<host>:<port>/<db>/
    # Le slash à la fin est indispensable !
    conf = config.set_xmlrpc('http://admin:admin@localhost:8000/coog/')

    APIParty = Model.get('api.party')
    bank = APIParty.bank_from_number({'number': '123425425'})
    print(bank)

Appel d'une API par HTTP
~~~~~~~~~~~~~~~~~~~~~~~~

Pour tester une API par HTTP il est possible d'utiliser un outil comme Postman.
Pour pouvoir correctement configurer l'environnement Postman il faut, dans un
premier temps, générer les fichiers d'environnement et de collection à l'aide
du script **test.sh** situé dans le package coog-gateway. Une fois les fichiers
générés il faut les importer dans Postman. Pour le fichier collection à l'aide
du bouton import situé en haut à gauche et pour le fichier **environment.json**
à l'aide du bouton représentant un engrenage en haut à droite.

Création d'une requête avec Postman
"""""""""""""""""""""""""""""""""""

Pour créer la requête avec Postman, il faut dans un premier temps sélectionner
le dossier adéquat (ou en créer un) et ajouter une nouvelle requête en lui
donnant un nom compréhensible. Il sera ensuite possible de sélectionner le type
de requête et de spécifier son url qui sera du type:
*{{AUTH_URL}}/api/v2/<nom_du_module>/<nom_dans_controller>*. Pour compléter la
requête, il est nécessaire d'ajouter un tocken ayant la valeur *{{tocken}}* dans
l'onglet **Authorization** ainsi qu'un body correspondant au schéma json attendu
en entrée par l'API dans l'onglet **Body**. Pour le body, on sélectionnera le
format raw en JSON pour pouvoir voir les erreurs de syntaxe.

Pour pouvoir envoyer la requête il faut d'abord envoyer une requête USER: LOGIN
de manière à recevoir un tocken d'identification. Une fois le tocken reçu il est
possible d'envoyer d'autres requêtes.

Il peut être utile d'ajouter un ou plusieurs exemples de requête à l'aide du lien
Exemples présent en haut à droite dans Postman.
