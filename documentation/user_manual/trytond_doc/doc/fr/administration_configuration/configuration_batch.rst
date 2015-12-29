Configuration des batches
=========================

Les batches sont configurables via un fichier spécifique à référencer dans
``trytond.conf`` e.g. ::

    [batch]
    config_file = /path/to/batch.conf

Le fichier ``batch.conf`` contient une section pour chaque batch nommée d'après
le nom du batch.
Pour avoir accès au paramétrage spécifique d'un batch donné, se référer à la
:doc:`documentation du batch en question<../batches>`.
Ci-dessous, énumération des options communes à tous les batches.

default
-------
Cette section définit les réglages par défaut communs à tous les batches.
Ces réglages peuvent aussi être modifiés dans les sections spécifiques à chaque
batch.

.. _filepath_template:

filepath_template
~~~~~~~~~~~~~~~~~
Expression définissant comment nommer les fichiers produits par le batch.
Le chemin défini sera concaténé à ``root_dir`` pour aboutir au chemin absolu.
Les paramètres suivants peuvent être utilisés :

- ``%{BATCHNAME}``: nom du batch
- ``%{FILENAME}``: nom du fichier (unique) par défaut
- ``%{TIMESTAMP}``: timestamp formaté suivant ``filepath_timestamp_format``

Défaut : ``%{BATCHNAME}/%{FILENAME}``

filepath_timestamp_format
~~~~~~~~~~~~~~~~~~~~~~~~~
Chaîne de spécification de format de date à utiliser pour générer un timestamp
(cf :ref:`filepath_template`).
Séquences de formatage disponibles sur http://unixhelp.ed.ac.uk/CGI/man-cgi?date

Défaut : ``%Y%m%d_%Hh%Mm%Ss``

root_dir
~~~~~~~~
Répertoire racine contenant tous les fichiers écrits par les batches.
**Cet attribut doit être défini manuellement.**

.. _split_mode:

split_mode
~~~~~~~~~~
Mode de division de la charge de travail entre les différents workers.
Les valeurs possibles sont :

- ``divide``: charge globale divisée en ``split_size`` groupes de tailles égales
- ``number``: charge globale divisée en groupes de ``split_size`` objets

Ces valeurs peuvent être préfixées de ``mono_`` (ex : ``mono_divide``). Dans ce
cas, le traitement sera executé par un seul process, qui lui-même découpera les
tâches au sein de transactions séparées. Cela permet de traiter le cas de
certains batchs forcément séquentiels sans avoir à reconfigurer celery pour
n'utiliser qu'un seul worker

Défaut : ``divide``

split_size
~~~~~~~~~~
cf :ref:`split_mode`

Défaut : autant que le nomber de workers threads défini par
``CELERYD_CONCURRENCY`` dans le fichier de configuration celery.

