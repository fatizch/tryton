=======================================================================
Comment créer un modèle de courrier pour envoyer des SMS via Primotexto
=======================================================================

Introduction
============
    - Dans un premier temps, il faut s'assurer que le module requis "report_engine_primotexto" est installé.
    - Ce module nécessite la présence de **deux nouvelles variables** sous une section **[primotexto]** dans la configuration serveur (voir `Configuration du serveur`_)
    - Vous devez être en possession d'un compte Primotexto_ et avoir généré une clef d'accès sur votre espace personnel

.. image :: images/generer_clef_primotexto.png

*Cliquer aux endroits numérotés sur l'impression écran afin de générer la clef d'accès.*

Configuration du serveur
========================
.. _`Configuration du serveur`:

1. Editer le fichier de configuration depuis coog-admin an lançant la commande **"./coog edit-app"**.
2. Ajouter les lignes suivantes::

    [primotexto]
    url = https://api.primotexto.com/v2/notification/messages/send
    key = votre_cle_primotexto
3. Supprimer le container et relancer le serveur.

- *Nb: L'url est susceptible de changer au cours du temps, le cas échéant, elle est disponible dans la* `documentation Primotexto`_

.. _`documentation Primotexto`: https://www.primotexto.com/api/sms/notification.asp

Configuration d'un modèle de courrier SMS
=========================================

Dans un premier temps, il faut créer un nouveau modèle de courrier, puis renseigner les champs du nouvel enregistrement en fonction des besoins.

.. image :: images/configurer_modele.png

Explications:
*************
Les champs "Libellé de l'envoyeur", "Numéro de téléphone", "Nom de la campagne", "Catégorie" et "Message" supportent les champs dynamiques de type "genshi_". (Voir la `documentation Coog sur les champs dynamiques`_)

.. _`documentation Coog sur les champs dynamiques`: ./utiliser_champ_genshi_tuto.html
.. _genshi: https://genshi.edgewall.org/wiki/Documentation

    - Le libellé envoyeur est obligatoire (entre 3 et 11 caractères) et doit être alphanumérique.
    - Le numéro de téléphone est obligatoire et peut être sous la forme de +33x xx xx xx xx ou 0x xx xx xx xx. (Avec ou sans espaces, ou bien avec des "." à la place des espaces)
    - Le champ "Nom de la campagne" permet d'effectuer du regroupement pour des statistiques globales sur des envois. (Une campagne doit être créée au préalable dans l'espace personnel Primotexto_.
    - La catégorie est une clef de recherche technique pour des requêtes.
    - Le champs message comporte le texte qui sera envoyé par SMS au destinataire.

Pour plus d'informations, se réferer à `la documentation primo texto`_

.. _`la documentation primo texto`: https://www.primotexto.com/api/sms/notification.asp
.. _Primotexto: https://www.primotexto.com/

Erreurs
=======

En cas d'erreur de paramétrage ou bien de donnée inconsistante envoyée au service Primotexto_, il est possible qu'une erreur soit levée.
Le cas échéant, vous pouvez récuperer la description de cette erreur dans `la table des erreurs primotexto`_ grace au code renvoyé par Coog.

.. _`la table des erreurs primotexto`: https://www.primotexto.com/api/plus/code_erreurs.asp
