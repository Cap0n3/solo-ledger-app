## SoloLedger - Description

---

Nous souhaitons créer une application web de comptabilité pour gérer nos activités indépendantes. Elle nous servira également de base de données pour nos élèves.

## Activités concernées

- Moi : cours de guitare
- Mon épouse : cours de chant
- Moi : développement web, à exclure du périmètre pour le moment

La comptabilité des cours de musique suivra une logique similaire pour nous deux. Mon activité de développement web obéit à des règles différentes et ne doit pas être prise en compte dans cette première version.

## Comptes utilisateurs et séparation des données

L'application doit proposer un compte utilisateur individuel pour chacun de nous. Après connexion, chacun doit pouvoir consulter et gérer les données de sa propre activité : élèves, formules, paiements et écritures comptables.

Les données doivent rester séparées entre nos deux comptes. Les mêmes principes de comptabilité peuvent s'appliquer aux cours de guitare et de chant, mais chacun ne doit accéder qu'à ses propres données.

La séparation est totale : aucun utilisateur ne peut consulter les données de l'autre. Chaque utilisateur tient sa propre comptabilité et importe les relevés de son propre compte bancaire.

## Objectif

L'application doit nous permettre de faire rapidement notre comptabilité chaque mois et de vérifier les paiements de nos élèves : savoir qui a payé et qui doit encore de l'argent.

Nous ne souhaitons pas utiliser d'API bancaire. Les paiements seront vérifiés à partir d'un export CSV de notre compte bancaire, que nous importerons directement dans l'application.

Après l'import, l'application devra comparer les crédits du compte avec les paiements attendus pour nos élèves, en tenant compte du nom de la personne qui a effectué le versement et des mois encore impayés. Elle devra indiquer les paiements identifiés, les montants encore dus et les éventuelles transactions qui nécessitent une vérification manuelle.

Toutes les écritures comptables doivent pouvoir être modifiées à tout moment.

## Fonctionnement du paiement des cours de musique

### Paiement

Le paiement des formules standards s'effectue à l'avance. Par exemple, le 28 mai, un élève paie les cours du mois de juin. La facture est établie et envoyée par e-mail au format PDF en dehors de l'application, et doit être payée dans les dix jours suivant sa réception, de préférence par virement bancaire.

L'application ne génère pas et n'envoie pas de factures.

### Année de cours et date de début

Chaque activité fonctionne par années de cours. Une année de cours typique s'étend de **septembre à juillet** : août n'est pas facturé. La reprise peut toutefois avoir lieu fin août ou en septembre selon l'activité et selon l'année.

Pour chaque activité et chaque année de cours, le premier et le dernier mois facturés doivent donc être paramétrables. Ils ne doivent pas être codés en dur.

Chaque élève a une date de début de cours et, s'il arrête, une date de fin de cours. Les paiements attendus ne sont générés qu'à partir du mois de la date de début, jusqu'au mois de la date de fin le cas échéant, et uniquement pour les mois facturés de l'année de cours.

### Début et fin en cours de mois

L'application ne calcule **aucun prorata**. Lorsqu'un élève commence ou arrête ses cours en milieu de mois, le paiement attendu de ce mois reste égal au montant complet de la formule.

Si l'élève paie un montant inférieur, le mois apparaît comme **partiellement payé**. L'utilisateur ajuste alors manuellement le montant attendu de ce mois.

Exemple : un élève commence le 15 octobre avec la formule à 280 CHF et ne suit que deux cours en octobre. Le paiement attendu d'octobre est de 280 CHF. L'élève paie 140 CHF : le paiement est signalé « à vérifier ». Après confirmation, octobre apparaît comme partiellement payé, et l'utilisateur modifie le montant attendu d'octobre à 140 CHF. Le mois passe alors au statut payé.

Un montant modifié manuellement n'est plus recalculé automatiquement.

Les vacances en cours d'année (automne, Noël, Pâques, etc.) ne modifient pas le montant mensuel.

### Année de cours et année fiscale

L'application distingue strictement deux notions de période, qui ne doivent jamais être confondues dans la logique :

- **L'année de cours** chevauche deux années civiles, par exemple de septembre 2026 à juillet 2027. Elle sert aux paiements attendus, à l'attribution des paiements aux mois, au suivi des impayés et des arriérés.
- **L'année fiscale** correspond à l'année civile, du 1er janvier au 31 décembre. Une recette appartient à l'année fiscale de sa **date de réception**, quel que soit le mois de cours qu'elle paie. Une dépense appartient à l'année fiscale de sa date de paiement.

Exemple : un paiement reçu le 28 décembre 2026 pour les cours de janvier 2027 est attribué au mois de janvier 2027 de l'année de cours 2026-2027, mais compte comme recette de l'année fiscale 2026.

Le compte d'exploitation et les statistiques financières (recettes, dépenses, résultat) se basent sur l'année fiscale et les dates de réception. Le suivi des paiements (attendus, payés, impayés, en retard, arriérés) se base sur l'année de cours.

### Création des paiements attendus

Les paiements attendus sont créés **automatiquement** par l'application :

- lorsqu'une formule est attribuée à un élève ou à un payeur, l'application crée les paiements attendus de tous les mois facturés de l'année de cours, de la date de début de l'élève jusqu'au dernier mois facturé ;
- lorsqu'une nouvelle année de cours est paramétrée, les paiements attendus sont créés pour les élèves qui poursuivent leurs cours ;
- lors d'un changement de formule, les paiements attendus des mois concernés sont mis à jour avec le nouveau montant, à partir du mois où le changement prend effet.

Les mois déjà payés, annulés ou modifiés manuellement ne sont jamais modifiés automatiquement. Chaque paiement attendu peut être corrigé manuellement.

### Attribution des paiements aux mois

Un paiement n'est pas rattaché au mois de sa réception, mais au **plus ancien mois encore impayé de l'année de cours concernée**, à partir de la date de début de cours de l'élève.

Un paiement reçu pendant la pause entre deux années de cours (par exemple en août, avec une année de septembre à juillet) est en principe rattaché à la nouvelle année.

### Cas non évidents : demander plutôt que deviner

Lorsque l'attribution d'un paiement n'est pas évidente, l'application ne l'attribue pas automatiquement. Elle le signale comme **« à vérifier »** et propose les choix possibles ; l'utilisateur décide.

Sont notamment considérés comme non évidents :

- un paiement reçu pendant la pause entre deux années alors que l'élève a un arriéré de l'année précédente (par exemple un paiement de juillet reçu en août) ;
- un montant qui ne correspond pas exactement à la mensualité due ou à un multiple exact de celle-ci, qu'il soit inférieur (paiement partiel) ou supérieur ;
- un payeur qui correspond à plusieurs élèves ou à aucun élève.

Dans les autres cas, l'attribution automatique s'applique, et elle reste toujours modifiable.

Les montants restés impayés d'une année de cours précédente ne sont jamais compensés automatiquement par un paiement de la nouvelle année. Ils restent visibles comme arriérés sur la fiche de l'élève et sur le tableau de bord, et peuvent être soldés uniquement par une attribution manuelle.

Exemple : Roger M., formule hebdomadaire à 280 CHF, début des cours en septembre.

| Date du paiement | Montant  | Mois attribué | Remarque          |
|------------------|----------|---------------|-------------------|
| 28 août          | 280 CHF  | septembre     | payé à l'avance   |
| 25 septembre     | 280 CHF  | octobre       | payé à l'avance   |
| (octobre)        | —        | —             | aucun paiement    |
| 24 novembre      | 280 CHF  | novembre      | payé en retard    |
| 28 novembre      | 280 CHF  | décembre      | payé à l'avance   |

Règles complémentaires :

- Un paiement d'un montant égal à plusieurs mensualités (par exemple 560 CHF) est réparti sur autant de mois impayés, du plus ancien au plus récent.
- Un paiement partiel est proposé pour le plus ancien mois impayé, mais signalé « à vérifier » : il n'est attribué qu'après confirmation par l'utilisateur. Le mois apparaît alors comme partiellement payé.
- Un paiement supérieur aux montants dus est conservé comme avoir et attribué aux mois suivants de la même année de cours.
- Un paiement en retard est signalé comme tel, sans bloquer l'attribution. Un mois est considéré en retard s'il n'est pas entièrement payé au **jour limite** du mois concerné. Ce jour limite est modifiable dans les paramètres ; sa valeur par défaut est le 10.
- L'attribution proposée peut toujours être corrigée manuellement. Une correction manuelle n'est jamais modifiée par l'attribution automatique.

### Annulation d'un mois

Dans certains cas, par exemple un accident ou une absence forcée, un élève ne paie pas un mois. Il doit être possible de marquer le paiement attendu de ce mois comme **annulé**, avec un motif facultatif.

Un mois annulé :

- n'est plus dû et n'apparaît pas dans les montants restant à percevoir ;
- est ignoré par l'attribution automatique des paiements, qui passe au mois impayé suivant ;
- reste visible sur la fiche de l'élève avec le statut « annulé » ;
- peut être rétabli si l'annulation était une erreur.

### Formules de cours

Plusieurs formules doivent pouvoir être créées et modifiées. Elles peuvent varier selon qu'elles concernent mon activité ou celle de mon épouse. Certaines anciennes formules sont encore utilisées par des élèves et doivent donc rester disponibles.

Pour chaque formule, nous devons pouvoir modifier le nom, la description et le prix, puis l'attribuer à un élève. Chaque élève ne peut avoir qu'une seule formule à la fois, mais peut en changer en cours d'année. Le changement prend alors effet au début d'un nouveau mois.

La modification du prix d'une formule ne doit pas modifier les paiements attendus ni les écritures déjà enregistrés.

Les formules mensuelles ont un tarif stable. Elles serviront à automatiser la création des paiements attendus et des écritures comptables. Les cours « à la carte », facturés à l'unité, seront saisis manuellement.

### Formule famille et payeurs

Plusieurs élèves d'une même famille peuvent être regroupés sous un **payeur** commun. La formule famille est attribuée à ce payeur et couvre tous les élèves qui lui sont rattachés : elle donne lieu à **un seul paiement attendu par mois**, et non à un paiement par élève.

Le nom de référence pour les paiements des élèves regroupés est porté par le payeur.

#### Mes formules (exemples)

- Nouvelle formule hebdomadaire : 280 CHF par mois
- Ancienne formule hebdomadaire : 260 CHF par mois
- Formule bimensuelle : 160 CHF par mois
- Pas de formule « à la carte » pour le moment

#### Formules de mon épouse (exemples)

- Nouvelle formule hebdomadaire : 340 CHF par mois
- Ancienne formule hebdomadaire : 320 CHF par mois
- Plus ancienne formule hebdomadaire : 300 CHF par mois
- Formule famille : 420 CHF par mois
- Formule bimensuelle : 180 CHF par mois
- Première ancienne formule bimensuelle : 170 CHF par mois
- Deuxième ancienne formule bimensuelle : 150 CHF par mois
- Formule « à la carte » : 90 CHF par cours

## Interface utilisateur

L'interface doit être en français, simple à prendre en main et conçue en priorité pour un ordinateur. Elle doit permettre de passer rapidement de la vue d'ensemble à la fiche d'un élève ou à une écriture comptable.

Un sélecteur de période doit être facilement accessible. Chaque utilisateur ne voit que les données de sa propre activité.

Les wireframes de référence se trouvent dans le dossier `docs/references/`.

### Navigation principale

L'application pourrait comporter les sections suivantes :

- **Tableau de bord** : résumé de la période sélectionnée, avec les montants attendus, reçus et encore dus, ainsi que les paiements à vérifier.
- **Élèves** : liste des élèves, accès à leur fiche et fonctions d'import et d'export CSV.
- **Formules** : gestion des formules de cours et de leurs tarifs.
- **Comptabilité** : consultation et modification des écritures comptables.
- **Dépenses** : saisie et consultation des dépenses, avec leur label, par exemple « Informatique » ou « Publicité ».
- **Import bancaire** : import des relevés CSV et vérification des transactions.
- **Statistiques** : consultation de statistiques utiles au suivi de notre activité indépendante.
- **Compte d'exploitation** : consultation et export du compte d'exploitation de l'activité, pour la période choisie, avec les recettes et les dépenses ventilées par label.
- **Paramètres** : gestion des informations du compte, notamment le numéro d'indépendant, le premier et le dernier mois facturés de chaque année de cours , le jour limite de paiement et les mots-clés servant à reconnaître les paiements d'élèves dans l'import bancaire.

### Tableau de bord mensuel

Le tableau de bord doit permettre de repérer immédiatement :

- les élèves dont le paiement est reçu ;
- les élèves qui n'ont pas encore payé ;
- les paiements reçus en retard ;
- les mois partiellement payés ;
- les arriérés des années de cours précédentes ;
- les paiements reçus dont l'origine ou l'attribution n'est pas certaine ;
- le total des montants attendus, reçus et restant à percevoir.

### Fiche d'un élève

Chaque fiche doit présenter les informations utiles sur l'élève, son activité, sa date de début de cours et, le cas échéant, sa date de fin, sa formule actuelle et l'historique de ses changements de formule. Elle doit aussi permettre de consulter ses paiements, ses écritures comptables et, le cas échéant, son payeur et les autres élèves rattachés au même payeur.

La fiche affiche, pour l'année de cours en cours, la situation mois par mois : montant attendu, paiement attribué (date et montant), statut (payé, en retard, partiellement payé, impayé, annulé). Les arriérés éventuels des années précédentes sont affichés séparément.

## Statistiques

L'onglet **Statistiques** doit permettre de consulter les indicateurs utiles au suivi de chaque activité, sur une période sélectionnée. Les données doivent être présentées séparément pour les cours de guitare et les cours de chant.

Les statistiques devraient notamment inclure :

- l'évolution des recettes dans le temps, par mois et par année ;
- les montants attendus, encaissés, annulés et restant dus ;
- le nombre d'élèves actifs, les nouvelles inscriptions et les départs sur la période ;
- la répartition des élèves par formule ;
- le total des dépenses, leur répartition par label et leur évolution dans le temps ;
- le résultat de l'activité, calculé à partir des recettes et des dépenses de la période.

Les indicateurs doivent préciser la période concernée et distinguer clairement les montants attendus des montants effectivement encaissés. Les indicateurs financiers (recettes, dépenses, résultat) se basent sur l'année fiscale ; les indicateurs de suivi des paiements et des élèves peuvent aussi être consultés par année de cours.

## Import et vérification des paiements

Après l'import d'un fichier CSV bancaire, les transactions doivent être présentées dans une liste claire. L'application peut proposer une correspondance avec un élève, mais toute correspondance incertaine doit être signalée pour vérification manuelle. Il doit être possible de confirmer ou de corriger une correspondance avant qu'elle soit considérée comme validée.

Une fois le paiement associé à un élève, il est attribué aux mois selon la règle décrite dans « Attribution des paiements aux mois ».

Un même relevé, ou des relevés couvrant des périodes qui se chevauchent, peuvent être importés plusieurs fois : les transactions déjà importées ne doivent pas être enregistrées en double.

### Nom de référence pour les paiements

Les transactions importées peuvent contenir plusieurs informations, notamment la date, le montant, le nom de la personne qui a effectué le paiement et le libellé du virement. Le nom du payeur peut être différent de celui de l'élève, par exemple lorsqu'un parent règle les cours d'un élève mineur.

Chaque fiche élève devra donc comporter, en plus du nom de l'élève, un champ modifiable **« Nom de référence pour les paiements »**. Ce nom servira à faciliter le rapprochement des transactions bancaires avec les élèves. Pour les élèves regroupés sous un payeur, c'est le nom de référence du payeur qui est utilisé.

## Import et export CSV des élèves

Depuis la section **Élèves**, il doit être possible d'exporter la liste des élèves au format CSV et d'importer un fichier CSV contenant des élèves.

L'application doit fournir un format simple et clairement défini, ainsi qu'un modèle CSV utilisable pour préparer les données. L'import doit afficher un aperçu des données et signaler les lignes ou les informations qui posent problème avant leur enregistrement.

L'import doit permettre d'ajouter des élèves et, lorsqu'un fichier exporté par l'application est réimporté avec des modifications, de mettre à jour les fiches correspondantes sans créer de doublons. Les élèves absents du fichier importé ne doivent pas être supprimés automatiquement.

L'import et l'export des élèves sont distincts de l'import des relevés bancaires.

## Structure du fichier CSV bancaire

Un fichier CSV bancaire d'exemple, contenant uniquement des données factices, est fourni dans `docs/references/export_mouvements.csv`. Il sert de référence pour le parser et de base pour les tests.

### Format actuel (export PostFinance)

- **En-tête de métadonnées** (lignes 1 à 5) : date de début, date de fin, catégorie, compte (IBAN) et monnaie, au format `Libellé:,valeur`.
- Une ligne vide, puis la **ligne d'en-tête des colonnes** : `Date`, `Type de transaction`, `Texte de notification`, `Crédit en CHF`, `Débit en CHF`, `Label`, `Catégorie`.
- Une ligne vide, puis les **transactions**, de la plus récente à la plus ancienne.
- Une ligne vide, puis un **pied de page** (`Disclaimer:` suivi d'un texte) à ignorer.
- Séparateur virgule ; les champs contenant une virgule sont entre guillemets.
- Dates au format `JJ.MM.AAAA`.
- Montants avec un point décimal, sans séparateur de milliers, parfois sans décimales (`320`, `-79.6`). Les crédits sont positifs dans `Crédit en CHF`, les débits négatifs dans `Débit en CHF`.
- Aucun identifiant unique de transaction n'est fourni.

### Texte de notification

Le nom du payeur et la communication sont contenus dans le champ `Texte de notification`, dans un texte libre :

- le nom du payeur suit `DONNEUR D'ORDRE:` ou `EXPÉDITEUR:`, suivi de son adresse ;
- la communication suit `COMMUNICATIONS:` ;
- l'ordre du nom et du prénom varie (`LEJUS ELISA`, `JEROME COCO`) : la comparaison avec le nom de référence ne doit pas dépendre de l'ordre des mots ;
- le texte contient parfois des coupures parasites au milieu des mots (`ALE XANDRE`) : la comparaison doit tolérer ces imperfections ;
- le texte est en majuscules et peut contenir des accents.

### Transactions non professionnelles

Le compte bancaire contient aussi des transactions sans rapport avec l'activité (achats personnels, assurances, transferts, subventions). L'application doit les écarter automatiquement et ne retenir que les transactions qui ressemblent à des paiements d'élèves.

- **Les débits sont ignorés.** L'import bancaire ne sert qu'au rapprochement des paiements d'élèves ; les dépenses sont toujours saisies manuellement.
- **Les crédits sont analysés** à l'aide de plusieurs signes distinctifs :
  - le nom du payeur correspond au nom de référence d'un élève ou d'un payeur (signe le plus fort) ;
  - le montant correspond à une mensualité attendue, à un multiple de celle-ci ou au prix d'une formule ;
  - la communication contient un mot-clé tel que « cours », « guitare », « guitar », « chant », « leçon », « lesson », « lessons » ou « MGR ». La liste des mots-clés est modifiable dans les paramètres. La recherche ignore les majuscules et les accents ;
  - la communication contient une référence de facture (par exemple `MGR-00736` ou `MG-000697`). Ces références ne sont pas toujours présentes ni toujours sous la même forme : elles renforcent une correspondance, mais ne sont jamais obligatoires.
- Un crédit qui ne présente **aucun** signe distinctif est classé automatiquement comme **non professionnel**.
- Un crédit qui présente des signes distinctifs sans correspondance certaine avec un élève est signalé « à vérifier ».

Les transactions classées non professionnelles restent consultables dans une liste séparée. L'utilisateur peut à tout moment reclasser une transaction comme paiement d'élève, ou marquer un crédit comme non professionnel.

Les autres éléments de la communication (par exemple un suffixe comme `26-27` ajouté par un élève) sont aléatoires et ne doivent pas être interprétés.

L'application ne vérifie pas l'IBAN du fichier importé.

### Doublons

En l'absence d'identifiant unique, une transaction est identifiée par la combinaison de sa date, de son montant et de son texte de notification. Deux transactions identiques dans un même fichier sont toutes deux conservées.

Cette structure peut évoluer au fil du temps, indépendamment de notre volonté. L'architecture doit donc isoler la logique de lecture et d'extraction des données afin qu'elle puisse être facilement adaptée si le format du fichier change.

## Gestion des dépenses

L'application doit permettre d'enregistrer nos dépenses professionnelles et de les associer à l'activité concernée.

Une sous-section **« Dépenses »** doit permettre de consulter et de gérer ces enregistrements. Les dépenses sont toujours saisies manuellement ; elles ne sont pas créées à partir de l'import bancaire. Les dépenses doivent être prises en compte dans la comptabilité de l'activité correspondante.

### Catégorisation des dépenses

Chaque dépense doit être associée à un label décrivant son type, par exemple « Informatique » ou « Publicité ». Les labels doivent pouvoir être gérés dans l'application afin que nous puissions les adapter à nos besoins.

## Modes de paiement

Chaque recette ou dépense doit pouvoir être associée à un mode de paiement, par exemple : virement bancaire, TWINT, espèces ou autre.

Les virements bancaires pourront être rapprochés des transactions importées depuis le fichier CSV. Les paiements en espèces et par TWINT devront pouvoir être saisis manuellement. Toutes les recettes et dépenses enregistrées doivent figurer dans la comptabilité et dans les totaux destinés au suivi fiscal.

## Compte d'exploitation

L'application doit permettre de consulter et d'exporter un compte d'exploitation pour une activité donnée et une période choisie. Les activités de cours de guitare et de chant doivent être présentées séparément.

Ce document servira notamment à préparer les éléments nécessaires à nos démarches fiscales. Il doit présenter les recettes, les dépenses ventilées par label, le total des dépenses et le résultat de la période.

Les recettes y sont comptabilisées selon leur date de réception, et les dépenses selon leur date de paiement, conformément à la règle décrite dans « Année de cours et année fiscale ».

Les paramètres doivent permettre d'enregistrer le numéro d'indépendant de chaque titulaire. Le numéro correspondant doit figurer sur le compte d'exploitation exporté.

Un exemple de compte d'exploitation au format PDF sera fourni afin de servir de référence pour la structure et la présentation du document.

> **Note :** mon activité de développement web reste exclue du périmètre actuel. La structure de l'application devra toutefois permettre de gérer séparément d'autres activités à l'avenir.

## Stack technique

L'application sera développée avec :

- **Python 3.14** ;
- **Django 6.1.2** pour le backend, les templates et les formulaires ;
- **PostgreSQL** pour la base de données ;
- **HTMX** pour mettre à jour certaines parties de l'interface sans rechargement complet de la page ;
- **Alpine.js** pour les interactions légères côté navigateur ;
- **Bootstrap 5.3.8** pour le style de l'interface (Bootstrap 6 n'existe qu'en version alpha) ;
- le système d'authentification intégré à Django.

Le Django Styleguide de HackSoft servira de référence pour organiser le code. Ses principes seront appliqués de manière pragmatique, notamment pour séparer les vues de la logique métier. Des services pourront gérer les opérations métier et des selectors les requêtes complexes, par exemple pour les imports CSV, le rapprochement des paiements, les statistiques et les comptes d'exploitation.

Chaque donnée liée à une activité devra être rattachée au compte utilisateur correspondant. Les requêtes et les modifications devront respecter cette séparation.

Le code (noms de modèles, champs, variables, fonctions) et les commentaires sont rédigés en anglais. Seuls les textes visibles par l'utilisateur sont en français. Le glossaire de correspondance entre les termes métier et les noms utilisés dans le code se trouve dans `CLAUDE.md`.

Le code Python utilise des annotations de types pour toutes les fonctions et méthodes, y compris leurs paramètres et leurs valeurs de retour. Les types sont vérifiés automatiquement avec mypy et django-stubs. Les règles détaillées se trouvent dans `CLAUDE.md`.

## Organisation du projet

Le projet suivra une structure Django organisée par domaines, avec un paquet de configuration séparé et un dossier `apps/` regroupant les applications métier.

L'organisation pourra s'inspirer de cette arborescence :

```
project/
├── manage.py
├── Dockerfile
├── compose.yaml
├── compose.dev.yaml
├── compose.prod.yaml
├── Makefile
├── package.json
├── package-lock.json
├── .devcontainer/
│   └── devcontainer.json
└── core/
    ├── config/
    │   ├── settings/
    │   │   ├── base.py
    │   │   ├── development.py
    │   │   ├── production.py
    │   │   └── test.py
    │   ├── urls.py
    │   ├── asgi.py
    │   └── wsgi.py
    ├── apps/
    │   ├── students/
    │   │   ├── apps.py
    │   │   └── admin.py
    │   ├── accounting/
    │   │   ├── apps.py
    │   │   └── admin.py
    │   ├── bank_imports/
    │   │   ├── apps.py
    │   │   └── admin.py
    │   └── reports/
    │       ├── apps.py
    │       └── admin.py
    ├── templates/
    ├── assets/
    │   ├── scss/
    │   │   └── app.scss
    │   └── js/
    │       └── app.js
    └── static/
        └── dist/
            ├── css/
            │   └── app.css
            └── js/
                └── app.js
```

## Environnement Docker

L'application et ses services devront pouvoir être lancés avec Docker Compose. Django et PostgreSQL fonctionneront dans des conteneurs séparés. Les données de PostgreSQL seront conservées dans un volume persistant.

Pour le développement, le projet devra être utilisable facilement depuis VS Code, idéalement avec un Dev Container. Le code source sera monté ou synchronisé dans le conteneur de développement afin que les modifications enregistrées dans VS Code soient immédiatement prises en compte par l'application. Les commandes de développement, comme le lancement du serveur Django, les migrations et la compilation des fichiers CSS et JavaScript, devront être accessibles depuis cet environnement.

La configuration de production devra utiliser des images Docker construites à partir du projet et des paramètres adaptés à la production. Le processus de build devra rester proche de celui du développement, avec une configuration distincte pour chaque environnement.

## Approche de développement et stratégie de tests

Le développement avancera par **tranches verticales** : chaque tranche correspond à une fonctionnalité complète, des modèles jusqu'à l'interface, utilisable dans le navigateur à la fin de la tranche. On ne commence une nouvelle tranche que lorsque la précédente est terminée, testée et validée.

### Étapes à l'intérieur de chaque tranche

1. **Modèles et règles métier**
   Définir les modèles, leurs relations et leurs contraintes. Écrire et exécuter les tests couvrant leurs validations et les règles métier de la tranche.

2. **Services, selectors, formulaires et vues**
   Implémenter la logique métier dans les services et les selectors, puis les formulaires et les vues. Tester la création et la modification des données, ainsi que la séparation des accès entre les comptes utilisateurs.

3. **Interface utilisateur**
   Réaliser les templates en s'appuyant sur les wireframes fournis. L'interface doit rester simple et facile à utiliser.

Chaque tranche se termine par :

- tous les tests au vert et le lint sans erreur ;
- la fonctionnalité utilisable dans le navigateur ;
- la commande de données fictives mise à jour pour couvrir la nouvelle fonctionnalité ;
- une validation manuelle avant de passer à la tranche suivante.

### Ordre des tranches

0. **Fondations**
   Environnement Docker (développement et Dev Container), configuration par environnement, Makefile, outils de lint et de tests, authentification, modèle d'activité rattaché à l'utilisateur et mécanisme de séparation des données. Page d'accueil après connexion et squelette de navigation.

1. **Élèves et formules**
   Gestion des formules par activité, fiches élèves avec dates de début et de fin de cours et nom de référence pour les paiements, payeurs et formule famille, attribution d'une formule et historique des changements de formule. Paramétrage des années de cours (premier et dernier mois facturés).

2. **Paiements attendus et écritures comptables**
   Création automatique des paiements attendus à partir des formules et des dates de début et de fin, annulation d'un mois, saisie manuelle des recettes (cours à la carte, espèces, TWINT), modes de paiement, attribution des paiements aux mois selon la règle du plus ancien mois impayé de l'année de cours, arriérés des années précédentes, consultation et modification des écritures, situation mois par mois sur la fiche élève.

3. **Dépenses**
   Saisie et consultation des dépenses, gestion des labels, rattachement à l'activité.

4. **Import bancaire et rapprochement**
   Lecture du CSV bancaire via un parser isolé, liste des transactions, proposition de correspondances avec les élèves, confirmation ou correction manuelle, attribution aux mois, détection des imports en double.

5. **Tableau de bord mensuel**
   Sélecteur de période, élèves ayant payé ou non, paiements en retard, paiements à vérifier, totaux attendus, reçus et restant dus.

6. **Import et export CSV des élèves**
   Modèle CSV, export, import avec aperçu, signalement des erreurs et mise à jour sans doublons.

7. **Compte d'exploitation et paramètres**
   Numéro d'indépendant dans les paramètres, compte d'exploitation par activité et par période, export PDF conforme à l'exemple fourni.

8. **Statistiques**
   Indicateurs par activité et par période, tels que décrits dans la section Statistiques.

9. **Mise en production**
   Configuration Docker de production, images construites, paramètres de sécurité, sauvegarde de la base de données.

### Principes de test

Les tests couvrent en priorité ce qui compte réellement : les règles métier, les calculs de montants, l'attribution des paiements aux mois, le rapprochement des paiements, la détection des paiements d'élèves parmi les transactions non professionnelles (à tester sur le fichier d'exemple), les cas limites des imports CSV et la séparation des données entre utilisateurs. On évite les tests qui ne font que vérifier le comportement standard de Django.

L'exemple de Roger M. décrit dans « Attribution des paiements aux mois » doit faire l'objet d'un test automatisé, ainsi que le passage d'une année de cours à la suivante avec un arriéré (un paiement reçu en août alors qu'un arriéré existe doit être signalé « à vérifier » et ne jamais solder l'arriéré automatiquement), un paiement incomplet pour un début en cours de mois suivi de l'ajustement manuel du montant attendu, et la distinction entre année de cours et année fiscale (un paiement reçu le 28 décembre pour janvier est attribué à janvier mais compte dans les recettes de l'année qui se termine).

## Outils de développement et données de test

Un **Makefile** devra regrouper les commandes courantes du projet afin de faciliter son utilisation, notamment les commandes pour lancer les tests, appliquer les migrations et démarrer l'application dans Docker.

Une commande Django de management devra permettre de générer des données fictives pour tester l'application : utilisateurs, élèves, formules, recettes et dépenses. Ces données devront être clairement identifiables comme des données de test et ne contenir aucune information réelle. La commande devra être documentée et facile à lancer depuis le Makefile.

## Références

Les images de référence des wireframes et l'export bancaire sont disponibles dans le dossier `docs/references/`.

Attention : l'export contient des transactions réelles et des données confidentielles. Il doit être traité avec précaution, ne pas être exposé ni partagé, et ne pas être inclus dans un dépôt ou un environnement accessible publiquement. Pour le développement et les tests, seule une copie anonymisée, de même structure, doit être utilisée.
