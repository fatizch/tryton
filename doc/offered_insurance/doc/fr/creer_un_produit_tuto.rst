
Paramétrer un nouveau produit
-----------------------------

Le but de ce tutoriel est d'expliquer les différentes étapes permettant de paramétrer un nouveau produit dans le laboratoire de Coog. Chaque étape est détaillée dans les sous-chapitres suivants.

Création du produit
...................

La première étape est de créer le nouveau produit. Depuis le menu |menu_produit| il est possible de consulter les produits existants et de créer un nouveau produit. Si le produit à créer est similaire à un produit existant, il est possible de le dupliquer.

.. |menu_produit| tryref:: offered.menu_product_form/complete_name

.. image :: images/produit-ecran-principal.png

Les informations obligatoires
,,,,,,,,,,,,,,,,,,,,,,,,,,,,,

Lors de la création d'un nouveau produit les éléments suivants vont devoir être renseigner avant de pourvoir enregistrer le produit.

- *le nom*: Nom du produit

- *le code*: Initialisé automatiquement à partir du nom. Ce code est unique dans l'application.

- *les dates de début et de fin de commercialisation*: seule la date de début de commercialisation est obligatoire

- *les types de risques couverts*: Ce type est paramétré dans l'application et est accessible depuis le menu |menu_risque|. Il est possible de rechercher un type de risque ou d'en créer un nouveau. Un produit peut porter sur différents type de risque. Sélectionner ou créer les types de risques qui correspondent au produit. 
    
.. |menu_risque| tryref:: offered.menu_item_desc_form/complete_name
    
.. image :: images/produit-risque-couvert.png
    
- *le générateur de numéro de contrat*: depuis l'onglet Administration sélectionner ou créer un nouveau générateur. Par défaut créer un nouveau générateur spécifique au produit.

- *le compte de facturation*: depuis l'onglet Administration sélectionner ou créer un compte de facturation. Ce compte de facturation est utilisé par la comptabilité. Par défaut créer un nouveau compte spécifique au produit de type 'Compte Produit'.

.. image :: images/produit-administration.png

Une fois ces informations complétées, il est possible d'enregistrer le produit.

Les données complémentaires
,,,,,,,,,,,,,,,,,,,,,,,,,,,

Les données complémentaires permettent de définir des informations supplémentaires qui vont être demandées lors de la souscription. Ces informations pourront ensuite être utilisées dans le moteur de règles.
Au niveau du produit on définit les données supplémentaires porter par le contrat. Ces données se définissent dans l'onglet Données complémentaires. Les questions suivantes peuvent aider à savoir si des données complémentaires sont nécessaires au niveau du contrat.

- Quels sont les critères tarifiants? Ce critère existe-t-il dans Coog? Si non, ce critère est-il global à un contrat? Si oui ce critère est potentiellement une donnée complémentaire à ajouter.
    Ex: Type de cotisation: Famille, Isolé, Adulte/Enfant...
- Existe-il des critères non tarifiants qui doivent être utilisé par une règle métier? Si oui ce critère existe-il dans l'application. Si non est-il global à un contrat. Si oui ce critère est potentiellement une donnée complémentaire à ajouter.

Une fois les données à ajouter identifiées, il est possible de les chercher ou de les créer.

.. image :: images/produit-donnees-complementaires.png

Les règles de gestion du contrat
,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,

L'onglet Règles permet de définir le comportement du contrat durant la souscription et la vie du contrat. Il est possible de définir les règles suivantes:

- *Règles d'éligibilité*: Qui a le droit de souscrire ce produit? Si tout le monde a le droit alors il n'est pas nécessaire de définir cette règle.
- *Règles de cotisation*: Existe-il un frais global au contrat ou une composante du tarif global au contrat? Si oui alors cette règle doit être renseignée.
- *Règles de franchise*: 
- *Clause*: le produit a-t-il des clauses globales au contrat? 
- *Documents*: des documents sont-ils demandés à la souscription? Si oui est-il global au contrat ou spécifique à une garantie. Si il est global au contrat alors le document peut être ajouter dans la règle.
- *Terme - Renouvellement*: Le contrat a-t-il un terme? Se renouvelle-t-il?

.. image :: images/produit-regles.png

Les méthodes de paiement
,,,,,,,,,,,,,,,,,,,,,,,,

L'onglet Méthodes de paiement permet de définir quels sont les moyens de paiement disponible lors de la souscription (ex: cheque, prélèvement...), quelles sont les fréquences de facturation disponible (ex: Mensuelle, Annuelle...). Plusieurs méthodes de paiement peuvent être définies. Pour créer une nouvelle méthode de paiement, il faut sauver le produit et aller dans le menu |menu_methode_paiement|.

.. |menu_methode_paiement| tryref:: billing_individual.menu_payment_method/complete_name

.. image :: images/produit-methode-paiement.png

Paramétrage des garanties
.........................
Les garanties peuvent être créées depuis le menu |menu_garantie| et ajoutées ensuite au produit ou depuis le produit dans l'onglet Garanties.

.. |menu_garantie| tryref:: offered.menu_coverage_form/complete_name

.. image :: images/produit-garantie.png

Les informations obligatoires
,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
Des informations sont nécessaires à la création d'un garantie.

- *Famille*: définie la famille de la garantie (ex: Prevoyance, Emprunteur...)
- *Nom*: Nom de la garantie
- *Code*: Initialisé automatiquement à partir du nom. Ce code est unique dans l'application.
- *les dates de début et de fin de commercialisation*: seule la date de début de commercialisation est obligatoire

.. image :: images/garantie.png

- *Compte de facturation* : depuis l'onglet Administration sélectionner ou créer un compte de facturation. Ce compte de facturation est utilisé par la comptabilité. Par défaut créer un nouveau compte spécifique au produit de type 'Compte Produit'.
- *Description du risque* : depuis l'onglet Administration sélectionner le type de risque couvert par cette garantie.

.. image :: images/garantie-administration.png

Les données complémentaires
,,,,,,,,,,,,,,,,,,,,,,,,,,,

De la même façon que des données supplémentaires peuvent être définies au niveau du contrat, des données peuvent être ajoutées au niveau de la garantie. Les questions suivantes peuvent aider à savoir si des données complémentaires sont nécessaires.

- Quels sont les critères tarifiants pour la garantie? Ce critère existe-t-il dans Coog? Si non, ce critère est-il lié à cette garantie? Si oui ce critère est potentiellement une donnée complémentaire à ajouter.
    Ex: Type de cotisation: Famille, Isolé, Adulte/Enfant...
- Existe-il des critères non tarifiants qui doivent être utilisé par une règle métier? Si oui ce critère existe-il dans l'application. Si non est-il spécifique à une garantie. Si oui ce critère est potentiellement une donnée complémentaire à ajouter.

.. image :: images/garantie-donnees-complementaires.png

Les dépendances entre garanties
,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,

L'onglet 'Souscription' permet de définir les dépendances entre garanties. Il est possible de définir qu'une garantie est obligatoire, optionnelle, proposée par défaut. Une garantie peut exclure d'autres garanties. Des garanties peuvent être requises pour souscrire la garantie.

.. image :: images/garantie-souscription.png

Les règles de gestion d'une garantie
,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,

L'onglet Règles permet de définir le comportement de la garantie durant la souscription et la vie de la garantie. Il est possible de définir les règles suivantes:

- *Règles d'éligibilité*: Qui a le droit de souscrire cette garantie produit? Si tout le monde a le droit alors il n'est pas nécessaire de définir cette règle.
- *Règles de cotisation*: Définie le tarif de la garantie
- *Règles de franchise*:
- *Clause*: le produit a-t-il des clauses globales au contrat?
- *Documents*: des documents sont-ils demandés à la souscription spécifiquement pour cette garantie? 

.. image :: images/garantie-regles.png

Les prestations
,,,,,,,,,,,,,,,

L'onglet prestation permet de définir les prestations disponibles lors de la déclaration d'un sinistre.

.. image :: images/garantie-prestation.png

Paramétrage des prestations
...........................

TODO