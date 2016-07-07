Batch de demande de documents [document.request]
================================================

Ce batch génère des courriers de relance pour toutes les demandes de documents
qui valident les critères suivants :

- document non réceptionné
- courrier de relance n'a pas été envoyé au cours des 3 derniers mois

Batch de relance de documents [batch.remind.documents]
======================================================
Ce batch émet l'évènement 'remind_documents' avec comme paramètre, les objets
sur lequel le batch est executé.
Il ne faut pas oublier d'associer dans les actions par type d'évènement,
l'évènement remind_documents avec une action (typiquement, un modèle de courrier
pour une impression)

Paramètres du batch:
on_model: le nom du modèle sur lequel le batch va s'exécuter (ex: contract)
remind_if_not: Le nom de/des champs à vérifier sur les lignes de document et
identifiant le besoin de relance ou non. (ex: received)
