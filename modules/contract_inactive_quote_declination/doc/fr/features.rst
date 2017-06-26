- **Batch de rejet des devis inactifs:**
    Ajoute d'un batch pour décliner les contrats qui valident les conditions suivantes:
    - status devis
    - La dernière date de modification du devis dépasse le delai maximum définit dans la configuration "Administration produit".
    En conséquence, le statut de ces contrats est passé à "Décliné".
    La raison de résiliation est définie en fonction du champs "Raison de la déclinaison automatique" dans la configuration "Administration produit".
