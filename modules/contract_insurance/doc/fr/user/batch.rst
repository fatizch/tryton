Batch de création en masse de demandes d'impressions [``report_production.contract_request.create``]
====================================================================================================

Ce batch permet de créer des demandes de production de document pour les
contrats correspondants aux critères :
- Actif à une date (paramètre ``treatment_date``)
- Ayant souscrit certains produits (paramètre ``products``)
- Une liste d'ids spécifique (paramètre ``contract_ids``)

Les documents sont générés avec le template passé en paramètre. Si ce template
accepte des paramètres supplémentaires, ils peuvent être ajoutés dans les
paramètres du batch (``--mon_parametre=ma_valeur``)

*Fréquence suggérée: manuelle*

