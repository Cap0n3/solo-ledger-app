# Documentation technique

Cette documentation explique comment SoloLedger est construit. Les trois autres documents du
dépôt gardent leur rôle : [SPECS.md](../SPECS.md) dit ce que l'application doit faire,
[CLAUDE.md](../CLAUDE.md) fixe les conventions de code, le [README](../README.md) couvre
l'installation et les commandes.

| Document                         | Contenu                                                                                   |
|----------------------------------|-------------------------------------------------------------------------------------------|
| [architecture.md](architecture.md) | Couches, cycle d'une requête, séparation des données, formulaires, front, outillage      |
| [domain.md](domain.md)           | Modèles et relations, règles métier implémentées, année de cours et année fiscale         |
| [decisions.md](decisions.md)     | Journal des décisions prises tranche par tranche, avec leur raison et l'alternative écartée |
| [references/](references/)       | Wireframes de référence (le CSV bancaire d'exemple n'est pas versionné)                   |

## Règles d'écriture

- Prose en français, identifiants de code en anglais, comme dans le reste du dépôt.
- `docs/` décrit l'implémentation et ses raisons. Une règle métier qui tient dans une fonction
  reste dans sa docstring ; ici on documente ce qui traverse plusieurs modules.
- Une tranche n'est terminée que lorsque ces documents reflètent le code. Chaque décision prise
  en préparant une tranche est ajoutée au journal, datée.
- Les schémas sont écrits en Mermaid, rendu nativement par GitHub et par VS Code.
