Batch de création des périodes d'indemnisation [``claim.indemnification.create``]
=================================================================================

Crée les périodes d'indemnisations jusqu'à la date passée en paramètre pour
toutes les prestations de type "rente" non terminées.

- *Fréquence suggérée:* quotidienne
- *Date de traitement à fournir:* date du jour


Batch de simulation de calcul des périodes d'indemnisation [``claim.indemnification.simulate``]
===============================================================================================

Simule la création de périodes de [N] jours et compare le montant avec la
précédente indemnisation sur le service délivré. Cela est utile pour
vérifier la cohérence de données migrées si il y a lieu.

- *Fréquence suggérée:* Après migration
- *job_size suggéré*: Taille d'une transaction / ~1000
- *Date de traitement à fournir:* Date du jour
- *revaluation / no_revaluation:* Activer ou non le calcul de revalorisation
- *filename:* Chemin absolu vers le fichier de sortie du résultat des simulations
- *duration:* Nombre d'unité pour la période de revalorisation à simuler
- *unit:* Unité de la période de revalorisation à simuler (day / month)
- *split:* Ne pas split le batch
