- **Configuration des jours fériés :** Il est possible d'ajouter manuellement 
    des jours fériés de trois catégories:

    - Jours fériés hebdomadaires: jours de repos de la semaine
        (généralement le weekend)
    - Jours fériés liés à Pâques: jours fériés dont la date dépend de celle de
        Pâques
    - Jours fériés fixes: jours fériés annuels jour/mois

- **Calcul du jour ouvré**: pour chaque configuration contenant un certain
    nombre de jours férié, il est possible de calculer un jour ouvré en sautant
    les jours fériés étant donné une date de départ, et un certain nombre de
    jours ouvrés.

- **Configuration des paramètres de batch**: Il est possible d'utiliser la
    classe 'work_days.configuration' pour calculer le paramètre 'treatment_date'
    des batchs où il est requis. Le calcul est fait selon les paramètres de
    batch suivants:

    - connection_date: date de départ. Par défaut elle est égale à la date
        d'aujourd'hui.
    - working_days: nombre de jours ouvrés.
    - conf_code: code de la configuration de jours fériés à utiliser.

    Avertissement: si le paramètre 'treatment_date' est spécifié pour un batch,
    sa valeur sera prise en compte et aucun calcul ne sera fait même si les
    paramètres ci dessus sont spécifiés.
