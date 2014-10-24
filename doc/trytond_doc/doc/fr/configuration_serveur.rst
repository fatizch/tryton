========================
Configuration du serveur
========================

La configuration du serveur Coog reprend les options de configurations du serveur Tryton et ajoute des sections supplémentaires.

sentry
------
Cette section définit la configuration de Sentry

homepage
~~~~~~~~
Spécifie le chemin vers la page d'accueil de Sentry (e.g: http://localhost:9000)

dsn
~~~
Clé d'api de sentry (e.g:  http://895c26f5b0384043b8a6919a7a26fefd:477f70118ef34e2ca6e308021b34b28a@localhost:9000/2)

batch
-----
Cette section définit la configuration des batchs

output_dir
~~~~~~~~~~
Spécifie le dossier des logs des batchs

EDM
---
Cette section définit des options de la GED.

server_shared_folder
~~~~~~~~~~~~~~~~~~~~
Définit le chemin depuis le serveur vers un répertoire temporaire qui doit être partagé avec le client. Ce répertoire est utilisé temporairement pour ouvrir un document en modification.

client_shared_folder
~~~~~~~~~~~~~~~~~~~~
Définit le chemin depuis le client vers le répertoire temporaire qui doit être partagé avec le serveur. Ce répertoire est utilisé temporairement pour ouvrir un document en modification.

options
-------
Cette section définit les options de Coog

table_dimension
~~~~~~~~~~~~~~~
Définit le nombre de dimensions maximum des tables du moteur de règles. Par défaut, le nombre de dimensions maximum est 4.

default_country
~~~~~~~~~~~~~~~
Définit le pays par défaut. Par défaut, le pays est la France.
