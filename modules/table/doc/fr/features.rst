La saisie des tables se fait en général via un import depuis un fichier csv,
ou bien par copier / coller. Pour les tables à plusieurs dimensions, il
est possible d'afficher les données sous forme d'un tableau à deux
dimensions, en fixant les valeurs des autres dimensions.


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
  visualiser ces données de deux façons :

  - Liste simple : chaque ligne de cette liste contient la valeur de chaque
    dimension, ainsi que la valeur résultante.

  - Tableau 2D : Affichage sour forme de tableau classique. Cette vue est utile
    pour les tables à 2 dimensions, et peut également être utilisée pour des
    tables à N dimensions en figeant les valeurs de N - 2 dimensions.

- **Index :** Un index étant une table à une dimension, ce module permet de
  les gérer correctement.
