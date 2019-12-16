La saisie des tables se fait en général via un import depuis un fichier csv,
ou bien par copier / coller.

- **Création de tables :** La création d'une table se fait en deux parties :

  - Saisie des données définissant la table (type de donnée, nombre de
    dimensions, valeurs possibles pour chaque dimension...)

  - Saisie du contenu de la table. Cette saisie peut se faire :

    - Via import / export de paramétrage **Coog**

    - Via import de fichier csv spécialement formaté

    - Via copier-coller des données

    - Manuellement, cellule par cellule (à limiter aux tables de petite taille)

- **Visualisation de tables :** Le contenu d'une table à plusieurs dimensions
  (plus de 2) peut être difficile à visualiser. Le module ``table`` permet de
  visualiser ces données sous forme de **liste simple** : chaque ligne de cette
  liste contient la valeur de chaque dimension, ainsi que la valeur résultante.

- **Index :** Un index étant une table à une dimension, ce module permet de
  les gérer correctement.
