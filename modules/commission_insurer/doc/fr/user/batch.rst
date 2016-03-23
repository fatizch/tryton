Batch de génération des bordereaux assureurs partie I [commission.invoice_principal.create_empty]
=================================================================================================

**Ce batch est la première étape dans le but de générer les bordereaux assureurs.**
Il doit être lancé en premier afin de pré-créer les quittances et lignes vides.
La date de lancement du batch est la date butoir utilisée pour la génération.
Le paramètre premium_line_description doit être renseigné dans le fichier de configuration

- *Fréquence suggérée:* mensuelle, le dernier jour du mois
- *premium_line_description (fichier de configuration):* Prime recue
- *job_size (fichier de configuration):* 0

Exemple de configuration :

.. code :: cfg

    [commission.invoice_principal.create_empty]
    premium_line_description = Primes Reçues
    job_size = 0


Batch de génération des bordereaux assureurs partie II [commission.invoice_principal.link]
==========================================================================================

**Ce second batch doit être lancé apres commission.invoice_principal.create_empty.**
Lie les mouvements comptables, lignes de quittance positives / négatives et les quittances.

- *Fréquence suggérée:* mensuelle, le dernier jour du mois
- *premium_line_description (fichier de configuration):* Prime recue
- *job_size (fichier de configuration):* 150
- *Nombre de workers:* autant que de coeurs disponibles


Batch de génération des bordereaux assureurs partie III [commission.invoice_principal.finalize]
===============================================================================================

**Ce troisième batch doit être lancé en dernier, apres commission.invoice_principal.link.**
Termine les bordereaux assureurs en assignant les montants sur les lignes des quittances.
Supprime les lignes intermédiaires temporaires.

- *Fréquence suggérée:* mensuelle, le dernier jour du mois
- *premium_line_description (fichier de configuration):* Doit être la même
  valeur que celle de la première partie du traitement.
- *job_size (fichier de configuration):* 0
