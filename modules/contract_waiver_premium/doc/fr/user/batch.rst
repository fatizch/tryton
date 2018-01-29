Batch de création de périodes d'exonération [``contract.waiver.create``]
========================================================================

Ce batch crée des périodes d'exonérations totales sur les contrats
sélectionnés. Les critères de sélections sont :
- Souscrit avant la date de traitement
- Actifs à un moment de la période concernée
- Souscrivant un des produits (optionnellement) passé en paramètres
- Une liste d'ids spécifique (paramètre ``contract_ids``)

Des périodes d'exonération correspondants aux dates passées en paramètres sont
alors créées pour toutes les garanties du contrat

*Fréquence suggérée: manuelle*
