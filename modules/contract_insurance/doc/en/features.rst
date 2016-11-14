- **Elément couvert :** Complète la modélisation du contrat avec la notion
  d'élément couvert. L'élément couvert représente la ou les entités assurées
  par le contrat. Il s'agira d'une personne (en prévoyance / santé), d'une
  haibtation (en MRH), d'une voiture (en auto), etc... Les éléments couverts
  sont directement rattachés au contrat et souscrivent des garanties
  indépendamment les uns des autres, avec des paramètres (franchise, ...)
  éventuellement différents.
  Ces éléments couverts sont modifiés en fonction des descripteurs de
  risque paramétrés et associés au produit (cf **offered_insurance**)

- **Surprimes :** Les surprimes sont un terme générique pour représenter les
  modifications de tarification. Il peut s'agir de majorations (pour cause
  d'analyse de risque défavorable, de malus, etc...) ou de réductions (
  souscription conjointe, réduction commerciale...).

- **Renouvellement :** Le contrat d'assurance est fréquemment renouvelé à
  l'échéance, ce module contient les outils permettant de gérer ce
  renouvellement.

- **Gestion des exclusions :** Le contrat prend en compte les exclusions
  définies dans le paramétrage des garanties pour limiter les possibilités de
  souscription.

- **Données complémentaires :** Les garanties souscrites peuvent maintenant
  renseigner les données complémentaires définies dans le paramétrage des
  garanties offertes associées via le module ``offered_insurance``.
