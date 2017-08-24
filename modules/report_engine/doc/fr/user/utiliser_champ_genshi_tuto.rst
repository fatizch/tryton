Syntaxe du répertoire d’export
==============================
Ce document explique comment remplir le répertoire d’export des modèles de courrier, mais également les autres champs qui supportent le texte “Genshi”.
----------------------------------------------------------------------------------------------------------------------------------------------------------------
    
    Afin d’apporter suffisamment de souplesse au paramétrage d’export des modèles de courrier, il a été nécessaire d’utiliser une syntaxe à mi-chemin entre langue commune et programmation.
    
    Il est donc possible d’écrire dans ce champ un chemin d'accès relatif comportant à la fois du texte plat **et** du texte dit “modèle” ou “variable” qui sera remplacé automatiquement en fonction du contexte dans lequel est imprimé le courrier.
    
    Cela permet donc d’avoir un chemin relatif qui évolue en fonction des enregistrements que l’on imprime (automatiquement ou manuellement), de la date du jour etc...
    
    La partie “variable” du texte se voit toujours préfixée par **${** et se termine par **}**.
    
    **Nb: Le texte "plat" dans la partie variable doit être entre doubles ou simples guillemets.**
    
Tutoriel
--------
    
    Dans notre scénario, nous souhaitons que le répertoire de sortie soit fonction de la date du jour, de l’adresse d'expédition et de certaines informations du tiers.
    Ce qui donne: [**Date du jour**]/[**Dossier Variable**]/[**Dossier Variable**]
    
    Pour récupérer la date du jour, il suffit d’utiliser "Today" (voir la liste des mots clés accessibles en fin de document) et comme nous sommes dans une partie de texte variable, il faut utiliser **${}**
    
    - **${Today}/**
    
    La deuxième partie qui est un nom de dossier variable est plus complexe car est soumise à la condition suivante:
    Si le tiers à qui nous envoyons le courrier a un email, alors le dossier sera “Envoi électronique” sinon, “Envoi postal”.
    Nous pouvons réaliser la condition de la manière suivante:
    
    - **${"Envoi electronique" if Party.email is not None else "Envoi postal"}**
    
    Ce qui peut se lire: *“Envoi électronique” si le mail du tiers n’est pas vide, sinon “Envoi postal”*
    
    Il en va de même pour la troisième partie de chemin qui dépend de la validité de l’adresse:
    
    - **${"NPAI" if Address.return_to_sender and Party.email is None else "VDC"}**
    
    Ce qui peut se lire: *“NPAI” si l’adresse est invalide ET que le tiers n’a pas d’email, sinon “VDC”*
    
    Le texte final est donc le suivant:
    
    - **${Today}/${"Envoi electronique" if Party.email is not None else "Envoi postal"}/${"NPAI" if Address.return_to_sender and Party.email is None else "VDC"}**
    
    Nb: **Pour accéder à un champs d’un objet dans du texte variable, il faut utiliser un “.”**
    
    Exemples: 
    
    - Party.name
    - Party.full_name 
    - Party.main_address.city
    
    Afin de connaître tous les champs accessibles d’un objet, il suffit d’aller dans le client Coog,
    **Menu administration** => **Modèles** => **Modèles** puis de chercher sur la description du modèle voulu. Tous les noms de champ seront visibles dans la vue formulaire de l’enregistrement sélectionné.

    .. image :: images/models_coog.png
    
    Des conditions complexes peuvent parfois nécessiter la réalisation à la volée d’une matrice.

    Exemple:

    +----------------------+----------------+
    | Code d’événement     | Nom de dossier |
    +======================+================+
    | activation_contrat   | ADH            |
    +----------------------+----------------+
    | application_avenant  | VDC            |
    +----------------------+----------------+
    | autre_evenement      | UKN            |
    +----------------------+----------------+

|

    Il est possible d'écrire une partie variable comme ceci:

    - **${{'activation_contrat': 'ADH', 'application_avenant': 'VDC', ‘autre_evenement’: ‘UKN’}.get(event_code, ‘N/A’)}**

    Le nom de dossier associé au code événement sera automatiquement retourné ou **N/A** si le code est introuvable dans la matrice prédéfinie.

Liste des variables ou fonctions accessibles depuis le texte variable pour les impressions
----------------------------------------------------------------------------------------
+-----------------+-------------------------------------------------------------------------------------+-------------------+---------------------+
| Nom             | Description                                                                         | Type              | Module requis       |
+-----------------+-------------------------------------------------------------------------------------+-------------------+---------------------+
| event_code      | Code de l’événement qui a provoqué la génération du courrier (peut être à None)     | texte             | De base             |
+-----------------+-------------------------------------------------------------------------------------+-------------------+---------------------+
| records         | List des objets à traiter                                                           | liste d'objet     | De base             |
+-----------------+-------------------------------------------------------------------------------------+-------------------+---------------------+
| record          | Premier objet de la liste                                                           | objet             | report_engine_email |
+-----------------+-------------------------------------------------------------------------------------+-------------------+---------------------+
| format_number   | format_number(valeur, langue, digits, grouping, monetary)                           | fonction          | De base             |
|                 | => Formate la valeur dans une langue avec le                                        | Retourne du texte |                     |
|                 | nombre souhaité de chiffre après la virgule.                                        |                   |                     |
|                 | Exemple: format_number(10, Party.lang, 4) donnera '10.0000' (grouping et monetary   |                   |                     |
|                 | ne sont pas obligatoires et que très rarement utilisés                              |                   |                     |
+-----------------+-------------------------------------------------------------------------------------+-------------------+---------------------+
| format_currency | format_currency(valeur, lang, currency, symbol)                                     | fonction          | De base             |
|                 | => Formate le montant dans la langue avec la                                        | Retourne du texte |                     |
|                 | devise et le symbole (True/False)                                                   |                   |                     |
+-----------------+-------------------------------------------------------------------------------------+-------------------+---------------------+
| format_date     | format_date(date, langue)                                                           | fonction          | De base             |
|                 | => Formate la date dans la langue donnée                                            | Retourne du texte |                     |
+-----------------+-------------------------------------------------------------------------------------+-------------------+---------------------+
| strftime        | strftime(date, format)                                                              | fonction          | report_engine       |
|                 | => Formatage technique d’une date,                                                  | Retourne du texte |                     |
|                 | voir https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior |                   |                     |
+-----------------+-------------------------------------------------------------------------------------+-------------------+---------------------+
| user            | L’utilisateur courant                                                               | objet             | report_engine       |
+-----------------+-------------------------------------------------------------------------------------+-------------------+---------------------+
| Today           | La date d'aujourd'hui                                                               | objet             | report_engine       |
+-----------------+-------------------------------------------------------------------------------------+-------------------+---------------------+
| round           | round(montant, nombre)                                                              | fonction          | report_engine       |
|                 | Retourne un arrondi, supporte les décimaux                                          |                   |                     |
+-----------------+-------------------------------------------------------------------------------------+-------------------+---------------------+
| Party           | Le tiers associé à l’opération                                                      | objet             | report_engine       |
+-----------------+-------------------------------------------------------------------------------------+-------------------+---------------------+
| Address         | L’adresse associée à l’opération                                                    | objet             | report_engine       |
+-----------------+-------------------------------------------------------------------------------------+-------------------+---------------------+
| Lang            | L’adresse associée à l’opération                                                    | objet             | report_engine       |
+-----------------+-------------------------------------------------------------------------------------+-------------------+---------------------+
| Sender          | L'émetteur associé à l’opération (peut être à None)                                 | objet             | report_engine       |
+-----------------+-------------------------------------------------------------------------------------+-------------------+---------------------+
| SenderAddress   | L’adresse de l'émetteur associée à l’opération (peut être à None)                   | objet             | report_engine       |
+-----------------+-------------------------------------------------------------------------------------+-------------------+---------------------+
| Decimal         | Permet de créer des decimaux ex:                                                    | Fonction          | report_engine       |
|                 | Decimal(‘10.000001’)                                                                | Retourne un objet |                     |
+-----------------+-------------------------------------------------------------------------------------+-------------------+---------------------+
| Company         | Retourne la société associée à l’opération                                          | objet             | report_engine       |
+-----------------+-------------------------------------------------------------------------------------+-------------------+---------------------+

