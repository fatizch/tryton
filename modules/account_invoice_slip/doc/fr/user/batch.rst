Batch de génération des bordereaux partie I [``account.invoice.slip.create_empty``]
===================================================================================

**Ce batch est la première étape dans le but de générer les bordereaux.**
Il doit être lancé en premier afin de pré-créer les quittances et lignes vides.
La date de lancement du batch est la date butoir utilisée pour la génération.

- *Fréquence suggérée:* mensuelle, le dernier jour du mois
- *job_size (fichier de configuration):* 0

Exemple de configuration :

.. code :: cfg

    [account.invoice.slip.create_empty]
    job_size = 0


Batch de génération des bordereaux partie II [``account.invoice.slip.link``]
============================================================================

**Ce second batch doit être lancé apres account.invoice.slip.create_empty.**
Lie les mouvements comptables, lignes de quittance positives / négatives et les quittances.

- *Fréquence suggérée:* mensuelle, le dernier jour du mois
- *job_size (fichier de configuration):* 150
- *Nombre de workers:* autant que de coeurs disponibles


Batch de génération des bordereaux partie III [``account.invoice.slip.finalize``]
=================================================================================

**Ce troisième batch doit être lancé en dernier, apres account.invoice.slip.link**
Termine les bordereaux assureurs en assignant les montants sur les lignes des quittances.
Supprime les lignes intermédiaires temporaires.

- *Fréquence suggérée:* mensuelle, le dernier jour du mois
- *job_size (fichier de configuration):* 0

Batch de génération des bordereaux assureurs partie I [``account.insurer_invoice.create_empty``]
================================================================================================

**Ce batch est la première étape dans le but de générer les bordereaux assureurs.**
Il doit être lancé en premier afin de pré-créer les quittances et lignes vides.
La date de lancement du batch est la date butoir utilisée pour la génération.

- *Fréquence suggérée:* mensuelle, le dernier jour du mois
- *job_size (fichier de configuration):* 0

Exemple de configuration :

.. code :: cfg

    [account.insurer_invoice.create_empty]
    job_size = 0


Batch de génération des bordereaux assureurs partie II [``account.insurer_invoice.link``]
=========================================================================================

**Ce second batch doit être lancé apres account.insurer_invoice.create_empty.**
Lie les mouvements comptables, lignes de quittance positives / négatives et les quittances.

- *Fréquence suggérée:* mensuelle, le dernier jour du mois
- *job_size (fichier de configuration):* 150
- *Nombre de workers:* autant que de coeurs disponibles


Batch de génération des bordereaux assureurs partie III [``account.insurer_invoice.finalize``]
==============================================================================================

**Ce troisième batch doit être lancé en dernier, apres account.insurer_invoice.link.**
Termine les bordereaux assureurs en assignant les montants sur les lignes des quittances.
Supprime les lignes intermédiaires temporaires.

- *Fréquence suggérée:* mensuelle, le dernier jour du mois
- *job_size (fichier de configuration):* 0
