Configuration
=============

Serveur
-------

Ecriture dans répertoire partagé
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Dans *trytond.cfg* faire pointer ``server_shared_folder`` vers un dossier monté
avec des droits en écriture pour l'utilisateur Unix de coog.

Dans le cas où l'on souhaite permettre l'édition du courrier .odt par
l'utilisateur, il faut renseigner le chemin ``client_shared_folder`` par lequel
le client accède au dossier partagé dans lequel le serveur écrit ::

    [EDM]
    server_shared_folder = /mnt/mail_documents
    client_shared_folder = F:\partage-serveur\mail_documents

(le client doit le cas échéant aussi avoir les droits en écriture sur le
dossier).

.. _server_export_root_dir:

Export dans un répertoire serveur
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Dans *trytond.cfg* faire pointer ``export_root_dir`` vers un dossier avec des
droits en écriture pour l'utilisateur Unix de coog. ::

    [report]
    export_root_dir = /share/documents

Génération du pdf
^^^^^^^^^^^^^^^^^

``gs`` doit être installé

.. code-block:: sh

    apt-get install ghostscript

Pour garantir une bonne fidélité du rendu, les polices d'écran utilisées dans
les templates LibreOffice doivent être présentes sur les pc serveur et client.

.. code-block:: sh

    cp ma-font.ttf /usr/share/fonts/type1/gsfonts/

Client
------

Envoi de mails
^^^^^^^^^^^^^^

Ligne de commande à renseigner dans *Options > Email...* pour paramétrer
l'envoi de mail, en fonction du client mail utilisé :

- Thunderbird ::

    thunderbird -compose "to=${to},subject=${subject},attachment=${attachment},body=${body}"

Export dans un répertoire spécifique par modèle de lettre
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

On peut paramétrer dans l'application pour chaque modèle de lettre un
sous-répertoire de *export_root_dir* (cf :ref:`server_export_root_dir`) dans
lequel écrire les documents générés :

- si aucun *Répertoire d'export* n'est renseigné alors pas d'export
- si ``/`` est saisi, alors les documents sont copiés directement à la racine,
  indiqué par le paramètre de configuration *export_root_dir*
- sinon le nom saisi est utilisé comme nom de sous-répertoire par rapport à 
  *export_root_dir*. Il est possible de renseigner une hiérarchie de dossiers, 
  auxquels cas les dossiers sont créés à la volée si non existants.

Exemple : avec le paramétrage de relance ci-dessous

.. image :: images/export_dir.png

Les documents de relance seront copiés dans le répertoire
``/share/documents/bin``.
