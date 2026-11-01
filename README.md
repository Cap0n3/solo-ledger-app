# SoloLedger

Application web de comptabilité et de suivi des élèves pour des activités indépendantes
d'enseignement musical (cours de guitare, cours de chant). Chaque utilisateur gère sa propre
activité et ne voit que ses données.

La spécification fonctionnelle se trouve dans `SPECS.md`, les conventions de code dans `CLAUDE.md`.
La documentation technique (architecture, modèle de domaine, journal des décisions) est dans
[`docs/`](docs/README.md).

## Prérequis

- Docker Desktop (Compose v2)
- `make` (fourni avec les outils en ligne de commande Xcode sur macOS)
- Pour le développement : VS Code avec l'extension *Dev Containers*

Aucune installation locale de Python ou de Node n'est nécessaire : tout tourne dans Docker.

## Démarrage rapide

```sh
make setup
```

Cette commande copie `.env.example` vers `.env` (si absent), construit l'image, démarre
PostgreSQL et Django, applique les migrations, installe les dépendances JS, compile les assets
et charge les données de test. L'application est ensuite disponible sur
<http://localhost:8000>.

### Comptes de test

Créés par `make seed` (mot de passe commun : `sololedger`) :

| Compte         | Rôle                                   | Activité          |
|----------------|----------------------------------------|-------------------|
| `test_guitar`  | utilisateur standard                   | Cours de guitare  |
| `test_singing` | utilisateur standard                   | Cours de chant    |
| `test_admin`   | superuser technique (accès à `/admin/`) | aucune            |

Chaque activité reçoit aussi ses formules (celles des exemples de `SPECS.md`), deux années de
cours (2025-2026 et 2026-2027), une douzaine d'élèves aux noms fictifs préfixés `[TEST]`, et des
payeurs dont une famille avec formule famille.

Ces données sont fictives et clairement identifiées par le préfixe `[TEST]`. La commande ne
fonctionne que si `SEED_ALLOWED` est vrai dans les settings (développement et tests uniquement).

Pour créer les vrais comptes : `make createsuperuser` pour le compte technique, puis créer les
utilisateurs et leurs activités dans `/admin/`.

## Développement avec VS Code (Dev Container)

1. Ouvrir le dossier dans VS Code.
2. Commande *Dev Containers: Reopen in Container*.
3. Dans le terminal du conteneur : `make run` pour lancer le serveur, `make test`, `make lint`.

Dans le Dev Container, le conteneur `web` ne lance pas le serveur automatiquement, afin qu'une
erreur dans les settings ne le fasse pas redémarrer en boucle. Depuis l'hôte (`make up`), le
serveur démarre tout seul.

Les sources sont montées dans le conteneur : toute modification est prise en compte
immédiatement par `runserver`. Les assets doivent être recompilés avec `make assets`
(ou `make assets-watch`).

## Commandes

`make help` liste toutes les cibles. Les plus courantes :

| Commande             | Effet                                                             |
|----------------------|-------------------------------------------------------------------|
| `make up` / `down`   | démarrer / arrêter la stack (hôte uniquement)                     |
| `make run`           | serveur de développement (depuis le Dev Container)                |
| `make migrate`       | appliquer les migrations                                          |
| `make migrations`    | créer les migrations                                              |
| `make test`          | lancer les tests (pytest, sur PostgreSQL)                         |
| `make lint`          | ruff, mypy, djlint, prettier, vérification des migrations         |
| `make format`        | formater tout le code                                             |
| `make assets`        | compiler SCSS et JS vers `core/static/dist/`                      |
| `make seed`          | charger les données de test                                       |
| `make shell`         | shell Django                                                      |
| `make lock`          | régénérer `uv.lock` après modification de `pyproject.toml`        |
| `make build`         | reconstruire l'image après `make lock` ou un changement du Dockerfile |
| `make reset-db`      | supprimer le volume PostgreSQL (toutes les données sont perdues)  |

Le Makefile détecte s'il tourne dans le conteneur : les mêmes commandes fonctionnent depuis
l'hôte (via `docker compose exec`) et depuis le Dev Container.

### Dépendances

- Python : modifier `pyproject.toml`, puis `make lock` et `make build`.
- JavaScript : `docker compose exec web npm install <paquet>` (ou `npm install` dans le Dev
  Container), puis `make assets`. `make npm` réinstalle les paquets quand `package-lock.json`
  a changé.

## Configuration

Les variables d'environnement sont lues depuis `.env` (voir `.env.example`). Les settings
Django sont découpés par environnement dans `core/config/settings/` : `development`
(défaut de `manage.py`), `test` (forcé par pytest) et `production` (toutes les valeurs
sensibles doivent venir de l'environnement).

## Données confidentielles

`docs/references/` contient les wireframes et un export bancaire d'exemple. Les fichiers CSV
de ce dossier ne sont jamais versionnés ni copiés dans l'image Docker.
