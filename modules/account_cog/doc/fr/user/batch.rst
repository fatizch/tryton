Batch de génération du rapport de la balance agée [``account.aged_balance.generate``]
=====================================================================================

Description :
-------------

Créé un rapport ODS de la balance agée en fonction des paramètres du batch.

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
    Date de départ des termes pour filtrer les lignes. (Date d'échéance <= date de traitement + terme)

- ``term1 (Entier, ex: 30)`` [obligatoire]
    Nombre de [unit] du premier terme.

- ``term2 (Entier, ex: 60)`` [obligatoire]
    Nombre de [unit] du second terme.

- ``term3 (Entier, ex: 90)`` [obligatoire]
    Nombre de [unit] du troisième terme.

- ``type (customer, supplier, customer_supplier)`` [obligatoire]
    Type de la balance (client, fournisseur ou bien les deux).

- ``unit (day, month)`` [obligatoire]
    Unité des termes (en jours ou en mois).

- ``output_dir`` [obligatoire]
    Chemin absolu vers le répertoire de sortie du batch (/chemin/de/sortie/).

- ``posted``
    Vrai par défaut. Pour mettre a faux: --posted=
    Si vrai: ne sort que les montant associés à un mouvement posté.

- ``possible_days (Liste d'entiers, ex: 12,15)``
    Liste des jours pour lesquels le batch va s'executer.
    Afin de ne pas executer le batch: Mettre --possible_days=

Le paramétrage doit être définit dans batch.conf comme qui suit:

::

    [account.aged_balance.generate]
    term1 = 30
    term2 = 60
    term3 = 90
    type = customer
    unit = day
    output_dir = /coog/data/io/batch/compta/
    possible_days = 12,15

Parallélisation:
----------------
Non supportée

Exemple :
---------
``coog batch exec account.aged_balance.generate 1 --treatment_date=$(date --iso)``
