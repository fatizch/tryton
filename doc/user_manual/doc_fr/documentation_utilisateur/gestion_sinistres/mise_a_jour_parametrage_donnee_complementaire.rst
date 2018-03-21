Comment ajouter une donnée complémentaire dans le paramétrage d'une prestation
==============================================================================

Description
-----------

Une fois en production, il arrive de vouloir faire évoluer le paramétrage des 
règles de prestation pour gérer un nouveau cas, une nouvelle règle. Cela peut 
nécessiter l'ajout de données complémentaires. Il faut alors mettre à jour les 
dossiers de prestations déjà créés afin d'initialiser les données ajoutées. 
Pour cela, Coog vient avec un assistant disponible depuis le paramétrage d'une 
prestation et depuis le paramétrage d'un type d'événement. Ce tutoriel a pour 
but d'expliquer le fonctionnement de cet assistant.

Étapes
------

Modification du paramétrage sur le type d'événement
+++++++++++++++++++++++++++++++++++++++++++++++++++

Nous souhaitons ajouter une nouvelle donnée complémentaire au niveau du 
paramétrage d'un type d'événement. Dans notre cas, nous ajoutons la donnée 
'Taux Incapacité Permanente'.

    .. image:: images/loss_desc.png

Une fois la donnée ajoutée, l'assistant de mise à jour peut être lancé depuis 
la barre de menu via le bouton "Actions/Propager les données complémentaires sur 
l'ensemble des préjudices"

    .. image:: images/update_wizard_step1.png

A la première étape, vous devez saisir la valeur par défaut de la donnée 
complémentaire que vous souhaitez initialiser. Vous pouvez enlever les données 
que vous ne souhaitez pas initialiser: dans tous les cas, l'assistant ne 
modifiera pas les valeurs existantes, il initialisera seulement si la donnée 
n'est pas présente.

Ensuite vous pouvez cliquer sur 'Propager' pour lancer l'initialisation des 
données complémentaires sur les préjudices.


Modification du paramétrage sur une prestation
++++++++++++++++++++++++++++++++++++++++++++++

Nous souhaitons ajouter une nouvelle donnée complémentaire au niveau du 
paramétrage d'une prestation. Dans notre cas, nous ajoutons la donnée 
'Nombre d'enfants à charge'.

    .. image:: images/benefit_extra_data.png

Une fois la donnée ajoutée, l'assistant de mise à jour peut être lancé depuis 
la barre de menu via le bouton "Actions/Propager les données complémentaires sur 
l'ensemble des services"

    .. image:: images/update_benefit_wizard_step1.png

A la première étape, vous devez saisir la valeur par défaut de la donnée 
complémentaire que vous souhaitez initialiser. Vous pouvez enlever les données 
que vous ne souhaitez pas initialiser: dans tous les cas, l'assistant ne 
modifiera pas les valeurs existantes, il initialisera seulement si la donnée 
n'est pas présente.

Ensuite vous pouvez cliquer sur 'Propager' pour lancer l'initialisation des 
données complémentaires sur les prestations exercées.
