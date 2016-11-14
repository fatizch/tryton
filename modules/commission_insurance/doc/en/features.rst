- **Plans de Commissionnement**

    - La *Méthode de commissionnement* permet de définir quand les commissions
      sont dues *A l'émission* ou *Au Paiement* de la quittance
    - Le *Type* de plan permet de différencier le plan de commissionnement de
      l'assureur et le plan de commissionnement du courtier
    - Le *Plan lié* permet d'associer à un plan de commissionnement courtier le
      plan de commissionnement assureur
    - Les *Lignes* permettent de définir pour un ensemble de garantie (qui
      peuvent être liées à des produits différents) la formule de commission à
      appliquer. Selon le paramétrage de la formule il est possible de calculer
      une commission linéaire ou en escompte (taux variant au fil du temps).
    - Les *Dates de calcul* permettent de spécifier à quelles dates le taux de
      commissionnement est susceptible de changer pour les différentes lignes,
      afin de retrouver les changements de taux aux bonnes dates dans les
      lignes de commission.

- Le **Protocole de commissionnement** est le lien entre un intermédiaire
  d'assurance (un assureur ou un courtier) et un plan de commissionnement
  associé.
  Le protocole peut avoir une date de début et une date de fin.

- L'**Assistant de création des protocoles de commissionnement** permet de
  saisir en masse pour un ensemble de courtier toutes les informations
  nécessaires pour calculer les différentes commissions

- L'**Assistant de génération des bordereaux de commissions** permet de générer
  les différents bordereaux des courtiers

- **Gestion des frais d'apporteur**: Un frais peut être typé frais d'apporteur.
  Le quittancement de ce frais va générer un credit dans le compte défini au
  niveau du frais. A la génération du bordereaux de l'apporteur, une ligne dans
  le bordereau sera généré pour tous les frais dont les quittances ont été
  payées.

- **Transfert de portefeuille**: Un point d'entrée dans l'application permet de
  transférer le portefeuille d'un courtier vers un autre. Ce transfert peut
  concerner la totalité des contrats, ou juste un sous-ensemble. Le transfert
  vérifie la compatibilité des protocoles de commissionnement entre le courtier
  d'origine et le nouveau courtier, et bloque les modifications en cas
  d'incompatibilité.
