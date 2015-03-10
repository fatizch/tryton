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

Ligne de commande à renseigner dans *Options > Email...* pour paramétrer
l'envoi de mail, en fonction du client mail utilisé :

- Thunderbird ::

    thunderbird -compose "to=${to},subject=${subject},attachment=${attachment},body=${body}"
