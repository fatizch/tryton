Configuration du serveur
========================

La configuration du serveur Coog reprend les options de configurations du serveur Tryton <http://doc.tryton.org/3.4/trytond/doc/topics/configuration.html> et y ajoute des sections supplémentaires.


trytond.conf
------------

batch
-----
Cette section définit les emplacements liés à la configuration des batches ::

    [batch]
    config_file = /path/to/batch.conf
    log_dir = /var/log/coop_batch/

- *config_file*: chemin vers le fichier .conf de configuration des batches
- *log_dir*: répertoire où les batchs écrivent leurs logs

EDM
---
Cette section définit des options de la GED::

    [EDM]
    server_shared_folder = /mnt/shared/disk
    client_shared_folder = /tmp

- *server_shared_folder*: chemin depuis le serveur vers un répertoire temporaire qui doit être partagé avec le client.
- *client_shared_folder*: le chemin depuis le client vers le répertoire temporaire qui doit être partagé avec le serveur. Ce répertoire est utilisé temporairement pour ouvrir un document en modification.

options
-------
Cette section définit les options de Coog ::

    [options]
    table_dimension = 10
    default_country = FR


- *table_dimension*: définit le nombre de dimensions maximum des tables du moteur de règles. Par défaut, le nombre de dimensions maximum est 4.
- *default_country*: définit le pays par défaut. Par défaut, le pays est la France.

sentry
------
Cette section définit la configuration de Sentry <https://sentry.readthedocs.org/en/latest> ::

    [sentry]
    homepage = http://localhost:9000
    dsn = http://895c26f5b0384043b8a6919a7a26fefd:477f70118ef34e2ca6e308021b34b28a@localhost:9000/2

- *homepage*: chemin vers la page d'accueil de Sentry (e.g: http://localhost:9000)
- *dsn*: clé d'api de sentry


