- **Gestion des portefeuilles de client**: Le référentiel de client peut être
  partitionné en plusieurs portefeuilles clients. Celui ci est matérialisé par
  un réseau de distribution auquel on affecte la propriété "Portefeuille
  Client".
  Chaque tiers créé dans l'application appartient à un portefeuille. Il peut
  alors être utilisé par tous les réseaux de distribution enfants du
  portefeuille.
  Le réseau de distribution par défaut d'un tiers est celui auquel est affecté
  l'utilisateur de l'application qui le crée. Si cette donnée n'existe pas, le
  réseau de distribution renseigné dans la configuration des tiers est utilisé.
