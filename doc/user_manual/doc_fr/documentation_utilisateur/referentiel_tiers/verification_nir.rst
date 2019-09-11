Comment activer la vérification du NIR à partir des informations de la personne
===============================================================================

L'objectif de ce tutoriel est de comprendre comment on peut activer dans Coog
la vérification du NIR sur la base des informations de la personne (date de
naissance, civilité, commune de naissance)

Paramétrage
-----------

L'activation de la vérification du NIR est possible depuis le point d'entrée
"Tiers" > "Configuration" > "Configuration des tiers" en cochant la case
"Vérification du NIR avec les informations de la personne". Dès lors à chaque
validation d'une personne le NIR sera vérifié.

Validation d'une personne
-------------------------

Dans cet exemple, la personne dont le NIR commence par un 1 est un homme.
Cependant, si on définit sa civilité à "Mme" alors on obtient le message non
bloquant suivant.

 .. image :: images/ssn_invalid_gender.png


