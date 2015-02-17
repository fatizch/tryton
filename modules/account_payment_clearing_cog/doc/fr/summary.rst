Ce module personnalise le module ``account_payment_clearing`` pour les besoins
du métier de l'assurance. Le module ``account_payment_clearing`` de tryton
offre les fonctionnalités suivantes:

- Gestion des mouvements comptables de compensation utilisé le temps des
  transactions bancaires (i.e transfert de la dette entre le client et
  l'établissement bancaire).

Ce module ajoute la description au mouvement comptable de compensation à partir
du nom du journal.  Il permet aussi de définir sur le journal de paiement si le
mouvement de compensation doit être émis automatiquement à la validation d'un
paiement.
