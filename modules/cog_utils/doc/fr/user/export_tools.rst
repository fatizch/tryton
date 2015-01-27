Outil d'export-import
=====================

L'outil d'export-import permet d'exporter et d'importer une configuration d'un
environnement Coog vers un autre. L'outil gère la création et la mise à jour.

A partir d'un objet, depuis le menu 'Lancer une action', l'action 'Export JSON'
lance l'assistant d'export. Celui ci propose d'utiliser une configuration
d'export qui peut être vide, puis exporte l'objet. Le fichier est alors
disponible pour sauvegarde et le détail des objets sauvegardés est affiché.

L'action 'Import JSON', aussi disponible depuis le menu 'Lancer une action',
prend en paramètre un fichier JSON et l'importe dans l'environnement.

L'import est aussi disponible depuis le menu 'Administation/Export
Import/Importer un fichier'.


Exports groupés
---------------
Cette fonctionnalité permet de regrouper un ensemble d'objets dans un même
fichier d'export via un package.

Depuis le menu 'Lancer une action', l'action 'Ajouter au package' ajoute
l'objet au package sélectionné.

Le menu 'Administation/Export Import/Exports groupés' regroupe les packages
créés. Ces packages peuvent être exportés suivant la méthode décrite ci dessus.
Le résultat sera un fichier JSON contenant l'ensemble des objets du package.

L'import d'un package se fait de la même façon que l'import d'un objet simple.


Configuration de l'export
-------------------------
Les informations exportées par l'outil d'export-import sont configurables
depuis le menu 'Administation/Export Import/Configuration'.

Une configuration d'export regroupe une ou plusieurs configuration d'export de
modèle. Chaque configuration de modèle permet de définir les champs que l'on
souhaite exporter pour un modèle précis.

L'option 'Exporter les objets maîtres en début de fichier' va exporter les
objets définis comme maître (ex: contrat, personne...) en début de fichier
plutôt que dans l'arborescence.

Le choix de la configuration à appliquer pour un export se fait dans
l'assistant d'export.


Outil d'export et web service de consultation
---------------------------------------------
L'outil d'export est aussi utilisé pour consulter n'importe quel objet de Coog
depuis l'extérieur via le web service ws_consult.

Exemple d'appel:

.. code :: python

        s = xmlrpclib.ServerProxy('http://%s:%s@%s:%s/%s' % (
                conf['user'], conf['password'], conf['server_address'],
                conf['port'], conf['db_name']))
        context = s.model.res.user.get_preferences(True, {})
        contract_information = {
            'Mon_id': {
                '_func_key': 'N0003'
                },
            }
        res = s.model.contract.ws_consult(contract_information, 'ma_config',
            context)

Ce web service prend en paramètre un dictionnaire avec les identifiants de
l'objet à rechercher et une configuration (celle ci est optionnelle).


La notion de func_key
---------------------
Chaque objet métier possède une clé fonctionnelle (func_key) qui permet
d'identifier de manière fonctionnelle un objet. Par exemple sur un contrat, la
clé fonctionnelle sera le numéro de contrat. Cette clé fonctionnelle est
utilisée lors de l'import pour savoir si Coog doit créer un nouvel objet ou
mettre à jour un objet existant. De même, elle est utilisée par le web_service
de consultation pour identifier l'objet à exporter.
