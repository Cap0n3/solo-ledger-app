# Journal des décisions

Une entrée par choix qui ne se déduit pas du code : ce qui a été décidé, pourquoi, et ce qui a
été écarté. Les entrées sont groupées par tranche, dans l'ordre chronologique. Une décision
revue reçoit une nouvelle entrée datée plutôt qu'une réécriture.

## Tranche 0, fondations (22 octobre 2026)

**L'entité métier s'appelle `Profession`, l'interface dit « activité ».**
Le premier nom, `Activity`, se lisait comme un journal d'actions de l'utilisateur dans
l'application. `Profession` désigne sans ambiguïté l'activité indépendante (guitare, chant).
Écartés : `Activity`, `Business`, `Workspace`. La migration initiale a été régénérée.

**Activité courante : la session, sinon la plus ancienne du compte.**
L'identifiant en session gagne tant que l'activité appartient toujours à l'utilisateur. Le repli
sur la plus ancienne reste stable quand on ajoute une activité plus tard. Écarté : une activité
par sous-domaine ou par préfixe d'URL, inutile pour un ou deux comptes.

**Modèle `User` personnalisé dès le départ, dans l'app `accounts`.**
Django le recommande : changer de modèle utilisateur après la première migration est très
coûteux. L'avatar et le nom d'affichage s'y sont ajoutés sans friction.

**Python 3.14, pas 3.15.**
Django 6.1 ne supporte officiellement 3.15 qu'à partir de 6.1.3, non publié à cette date. À
revoir à sa sortie : Dockerfile, `pyproject.toml`, `CLAUDE.md`.

**Bootstrap 5.3.8.**
La version 6 n'existait qu'en alpha sur npm.

**uv pour Python, Node 24 copié dans l'image Django pour les assets.**
Une seule image, pas de conteneur Node séparé. SCSS compilé par dart-sass, JS par esbuild.
Écartés : django-compressor, Bootstrap par CDN (SCSS personnalisable voulu).

**Settings découpés par environnement ; `DJANGO_SETTINGS_MODULE` jamais dans `.env`.**
`manage.py` prend `development`, pytest force `test`. Un `.env` unique ne peut ainsi pas faire
tourner les tests sur la base de développement.

**Makefile utilisable depuis l'hôte et depuis le conteneur.**
`IN_CONTAINER=1` bascule entre exécution directe et `docker compose exec` ; `-T` est ajouté
automatiquement hors terminal. Les cibles qui gèrent la stack refusent de tourner dans le
conteneur. Le Dev Container ne lance pas le serveur au démarrage pour qu'une erreur de settings
ne le fasse pas boucler.

**Admin Django activé, réservé à un compte technique.**
Il sert à créer les vrais comptes et leurs activités. Aucune page métier ne passe par lui.

**`django-stubs-ext` en dépendance d'exécution.**
Les settings activent son monkeypatch pour que `ModelAdmin[Profession]` soit valide au runtime
et pas seulement pour mypy.

**Factories appelées par `.create()`.**
factory_boy livre un `py.typed` mais son appel de métaclasse n'est pas typé ; `Factory()` ferait
échouer mypy strict. Les tests relâchent `disallow_untyped_calls`.

**Messages de commit en anglais, sans ligne d'attribution.**
Comme tout le code. L'historique a été nettoyé de toute ligne `Co-Authored-By`.

## Tranche 1, élèves et formules (1er novembre 2026)

**La formule famille et les formules individuelles coexistent.**
Un payeur peut porter une formule famille et un de ses élèves une formule propre en plus ; les
paiements attendus s'additionneront. Écartée : une règle d'exclusivité à valider, qui aurait
empêché le cas réel d'un enfant avec un cours à la carte en plus de la formule famille.

**Statut explicite de l'élève, avec « en pause » ; la date de fin fait foi.**
`Student.status` vaut `active`, `paused` ou `ended`. `end_date` est la borne de facturation ;
le statut est informatif, sauf `ended` qui exige une date de fin. L'effet de `paused` sur les
paiements attendus sera décidé avec la gestion des paiements. Écarté : un statut dérivé des
dates, qui ne pouvait pas exprimer la pause.

**Coordonnées minimales.**
Prénom, nom, e-mail, téléphone, notes, dates et nom de référence. Pas d'adresse postale ni de
date de naissance : la facturation se fait hors de l'application.

**Une page Payeurs et une fiche payeur.**
Sous la section Élèves du menu. Le payeur se choisit aussi depuis le formulaire élève. Écarté :
gérer les payeurs uniquement depuis les fiches élèves, trop indirect pour la formule famille.

**Type de formule `monthly` ou `single_lesson`.**
Un cours à la carte est attribuable à un élève mais jamais à un payeur, et ne génèrera jamais de
paiement attendu.

**Archivage plutôt que suppression ; pas d'historique des prix.**
Une formule déjà attribuée s'archive. Les montants seront copiés sur les enregistrements qui
les portent (paiements attendus, écritures), ce qui rend l'historique des prix inutile.

**Le nom de référence du payeur l'emporte.**
Avec ou sans formule famille : c'est le payeur qui vire l'argent, c'est donc son nom qui
apparaît sur le relevé.

**Un seul modèle `PlanAssignment`, cible élève ou payeur.**
Contrainte « exactement une cible » en base. `starts_on` au premier jour du mois, `ends_on`
facultatif. Au plus une attribution par cible et par mois de début. Écartés : deux modèles
séparés (logique dupliquée), ou une clé générique (moins typée).

**Règles de changement de formule.**
Un changement prend effet au début d'un mois et ferme la précédente le mois d'avant. Un
changement le même mois corrige en place. Une attribution postérieure doit être supprimée
d'abord. La dernière attribution peut être terminée à un mois donné, ou supprimée ; la
suppression ne rouvre la précédente que si ce changement l'avait fermée.

**Pas de suppression d'élève ; payeur supprimable seulement s'il est vide.**
Conformément à la règle du projet de ne jamais perdre de données utilisateur.

**`LessonYear` vit dans `accounts`, pas dans `students`.**
C'est un paramètre de l'activité, géré dans Paramètres comme le seront le jour limite de
paiement et les mots-clés. Le déplacer plus tard coûterait une migration entre apps.

**Mois saisis par deux listes déroulantes (`MonthField`).**
`<input type="month">` n'est pas supporté par Safari ni Firefox sur ordinateur.

**Dates saisies au format ISO.**
`<input type="date">` exige `YYYY-MM-DD` ; le format `fr_CH` par défaut viderait le champ.

**Montants affichés par un filtre `chf` dédié.**
`USE_THOUSAND_SEPARATOR` aurait aussi formaté les années (« 2’026 »). Le filtre produit
`1’234.50 CHF` avec une espace insécable.

**Liste des élèves : actifs et en pause par défaut, 25 par page, HTMX avec repli sans JavaScript.**
Les élèves terminés restent accessibles par le filtre. La restauration d'historique du
navigateur rend la page complète et la réponse porte `Vary: HX-Request`.

## Après la tranche 1 (1er novembre 2026)

**L'activité courante s'affiche en texte dans la barre latérale.**
La pastille dans l'en-tête des pages ressemblait à un bouton. Le nom se lit maintenant sous
« Comptabilité des cours », comme un contexte et non une action.

**Confirmation avant de supprimer une attribution, avec le résultat concret.**
La fenêtre nomme l'attribution retirée et la formule qui redeviendra en cours, ou dit qu'aucune
ne prendra le relais. La règle de réouverture a été déplacée dans un selector partagé par le
service et la fenêtre, pour qu'ils ne puissent pas se contredire. Écartée : une phrase
générique expliquant la règle, jugée incompréhensible.

**Documentation technique en Markdown dans `docs/`, sans outil.**
Prose en français, identifiants en anglais, schémas Mermaid rendus par GitHub et VS Code. Mise à
jour exigée à la fin de chaque tranche. Écartés pour l'instant : MkDocs (possible plus tard sur
les mêmes fichiers), Sphinx (disproportionné), génération automatique de l'API (les docstrings
suffisent).

## Préparation de la tranche 2 (13 novembre 2026)

**Les bons cadeaux et les cours à la carte sont des recettes ponctuelles, saisies librement.**
Un bon cadeau est payé une fois, souvent par quelqu'un qui n'est ni élève ni payeur, et ne
suit aucun rythme mensuel. La recette porte une date, un montant, un mode de paiement et un
libellé libre ; elle n'est attribuée à aucun mois et ne solde jamais une mensualité ni un
arriéré. Le lien avec un élève est facultatif : vide pour un bon acheté avant que le
bénéficiaire ait une fiche, rempli pour un cours à la carte qui doit apparaître sur la fiche.
Écartés : une formule « bon cadeau » (une formule sert à créer des paiements attendus, il n'y
en a pas ici), le décompte des cours consommés sur un bon, et un type dédié pour les
statistiques (le libellé suffit).

**Un élève sans formule n'a aucun paiement attendu.**
Le bénéficiaire d'un bon cadeau peut avoir une fiche avant de s'inscrire à une formule
normale. Les paiements attendus commencent au mois de prise d'effet de sa première formule.
