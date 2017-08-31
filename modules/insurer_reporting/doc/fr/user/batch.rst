Batch de génération du stock assureur [``insurer_reporting.contract.generate``]
===============================================================================

Description :
-------------

Génère les rapports de stock assureurs pour tous les assureurs avec au moins un modèle de courrier paramétré.

Dépendances :
-------------
Aucune

Fréquence :
-----------
La fréquence est gérée dans la chaîne journalière:
- A minima, la génération est effectuée le dernier jour du mois en cours.
- Le paramétrage dans batch.conf (possible_days=) permet de définir la liste des jours supplémentaires de génération du rapport (ex: 12,15). Il suffit de ne pas spécifier 'possible_days' dans batch.conf pour ne pas générer de rapport en plus chaque mois.

Paramètres d'entrée :
---------------------
- ``treatment_date (YYYY-MM-DD)`` [obligatoire]
    Date de traitement (Utilisé dans le nommage du fichier de sortie et pour l'écriture de la date dans le rapport)

- ``products (Liste des codes produits filtrants séparés par des virgules, ex: PRD1,PRD2)``
    Si définie, la liste des produits appliqueront un filtre sur le produit associé aux garanties de l'assureur.

- ``possible_days (Liste d'entiers, ex: 12,15)``
    Liste des jours pour lequel le batch va s'executer.
    Afin de ne pas executer le batch: Mettre --possible_days=

Le paramétrage doit être définit dans batch.conf comme qui suit:

::

    [insurer_reporting.contract.generate]
    products =
    possible_days = 12,15

Parallélisation:
----------------
Supportée (Une tâche par assureur)

Exemple :
---------
``coog batch exec insurer_reporting.contract.generate 1 --treatment_date=$(date --iso)``
