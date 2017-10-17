Impression du courrier
======================

L'action est accessible via le bouton *Actions* puis *Impression du courrier*.

Le premier écran permet de sélectionner les différents modèles de documents à
imprimer.
Si plusieurs modèles sont sélectionnés, le nom par défaut donné au fichier pdf
généré est le numéro de contrat (le nom peut être édité)
Les modèles peuvent être édités via un traitement de texte externe ou
accessibles uniquement en lecture, suivant la configuration de coog (cf
:ref:`configuration`).
Chaque fichier odt est individuellement converti vers le format pdf, puis les
pdf sont fusionnés pour constituer un unique fichier.
Si l'un des modèles utilisés a l'attribut "GED interne" coché, alors le pdf est
ajouté à la GED interne de coog.

.. _configuration:

Configuration
-------------
Les outils *gs* et *unoconv* doivent être présents sur le serveur.
Dans *trytond.cfg*, renseigner pour ``server_shared_folder`` un dossier avec
des droits en écriture.
Si l'utilisateur doit pouvoir éditer les modèles de lettre, il faut alors que
``client_shared_folder`` pointe vers le montage du dossier partagé sur la
machine client avec aussi des permissions en écriture ::

    [EDM]
    server_shared_folder = /mnt/mail_documents
    client_shared_folder = F:\partage-serveur\mail_documents
