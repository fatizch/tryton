Module contract_set
===================

Le module contract_set permet de définir un lien entre plusieurs contrats via
l'objet 'Groupe de contrat'. L'objet 'Groupe de contrat' contient un
identifiant unique.

Le module ajoute des données métiers au moteur de règles qui permettent
d'utiliser les informations des contrats liés :

- Numéro de la relation dans groupe de contrat (nom de la relation): cette donnée regarde sur le contrat et les contrats liés la place de la personne
selon l'ordre de naissance du plus vieux au plus jeune et parmi les personnes
avec la même relation.
- Nombre de personnes couvertes avec la relation dans groupe de contrat
(nom de la relation): permet de connaître le nombre de personnes couvertes sur
l'ensemble des contrats liés avec la relation définie en paramètre.

