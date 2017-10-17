Paramétrage
===========

Section à ajouter à *trytond.conf*  ::

    [migration]
    database = source_db
    user = tryton
    password = xxx
    host = 10.123.456.789
    schema = schema_if_needed


Architecture
============

Une migration consiste en une succession de batches migrant les données
modèle par modèle.
Un batch de migration hérite forcément du modèle Migrator.

Etapes de migration
-------------------

L'exécution d'un batch migration se fait en trois phases :

- requête de sélection des lignes à migrer
- requête de récupération des données à migrer
- création des objets coog à partir des données

La finalité des deux premières étapes est d'obtenir une liste de dicts
(par job) contenant les données source à migrer, le format des dictionnaires
étant défini par le migrator.
Plus la table source s'éloigne de la définition "idéale", plus la quantité de
code à surcharger va être importante.

La troisième étape prend des dictionnaires en entrée et créé pour chaque une
instance du modèle cible en sortie. On travaille sur des données normalisées,
pas de surcharge nécessaire a priori.

Sélection des lignes à migrer
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

La structure de table par défaut (cls.table et cls.columns) requêtée par un
objet Migrator reflète le modèle coog

exemple: pour migrer un tiers, on requête une table 'party' avec des colonnes
'name', 'first_name', etc.

Différentes surcharges sont à faire selon l'écart par rapport à ce cas
"idéal" :

- même structure de table mais le nommage des colonnes diffère : renseigner le
  nom de table utilisée et le mapping des colonnes dans __setup__().
- différente structure : un JOIN est nécessaire par exemple. Il faut surcharger
  select_ids(), select_columns() et query_data().

Objets Migrator
---------------

__setup__() : configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^

- cls.table, cls.columns : à renseigner afin d'avoir le mode par défaut de
  sélection d'ids, ie le chargement de tous les ids d'une table donnée
- cls.model, cls.func_key : si renseigné alors deux modes de migration sont 
  disponibles suivant la valeur du flag --update de la ligne de commande :
    - --update 0: sont alors exclus de la sélection d'ids à migrer les ids
      des enregistrements déjà présents en base destination
    - --update 1: les enregistrements déjà présents en base destination sont mis
      à jour si nécessaire
- cls.transcoding : à renseigner pour transcoder des valeurs récupérées dans la
  base source vers des valeurs attendues par coog.
  exemple: transcodage du *genre* pour un tiers

  .. code:: python

      cls.namings.update({'gender': {u'mr': 'male', u'mme': 'female',
        None: 'male'}})

select_ids() : sélection des ids à migrer
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- en générique: l'ensemble des ids est contruit à partir d'un
  dictionnaire regroupant les paramètres passés au batch, les modes suivants
  sont gérés :

  - `in`: liste des identifiants à migrer est passée sur la ligne de commande
  - `in-file`: liste des identifiants à migrer chargée à partir d'un fichier
    .py
  - `not-in`: liste des identifiants à exclure est passée sur la ligne de
    commande
  - `not-in-file`: liste des identifiants à exclure chargée à partir d'un
    fichier .py

  si ni `in` `in-file` ne sont pas passés en paramètre alors tous les ids de la
  table source cls.table sont chargés (mode par défaut)

- en custom: surcharger select_ids() pour retourner une autre liste
  d'ids en fonction des paramètres d'entrée du batch.
  Typiquement si on souhaite migrer une partie d'une table en fonction de la
  valeur d'une des colonnes (exemple: migrer table 'tiers' si
  'est_personne' = 't'), ce doit être fait en spécifique


code spécifique projet
^^^^^^^^^^^^^^^^^^^^^^

Pour chaque objet Migrator, le __setup__ est à surcharger en spécifique pour
configurer les données d'entrée/sortie : noms de table, colonnes,
transcodage de valeurs enumérées, codes erreurs possibles.

Et au cas par cas :

    - select_ids(), select_columns() et query_data() : fonctions impliquées
      dans le requêtage des données source
    - sanitize : reformatage/nettoyage des données récupérées,
      suppression des lignes inconsistantes de la liste des lignes à migrer
    - init_cache: mise en cache des objets intermédiaires requis pour migrer
      les lignes
      exemple: mise en cache des tiers souscripteurs lors de la migration des
      contrats
    - populate: pour stocker des champs additionnels dans
      l'objet ou "résoudre" des champs c'est à dire passer d'un code à une
      instance d'enregistrement en la récupérant dans le cache
    - migrate_rows: création des objets coog à partir des dictionnaires source