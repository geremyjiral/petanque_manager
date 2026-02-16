# Migrations de la base de données

## Migration 001: Rôles multiples pour les joueurs

Cette migration permet aux joueurs d'avoir plusieurs rôles au lieu d'un seul.

### Changements

- **Avant** : Chaque joueur a un seul rôle (`role` VARCHAR)
  - Valeurs possibles : `Tireur`, `Pointeur`, `Milieu`, `Pointeur/Milieu`

- **Après** : Chaque joueur a une liste de rôles (`roles` JSONB)
  - Valeurs possibles : `["Tireur"]`, `["Pointeur", "Milieu"]`, etc.
  - Un joueur peut avoir 1, 2 ou 3 rôles

### Conversion automatique

La migration convertit automatiquement :
- `Tireur` → `["Tireur"]`
- `Pointeur` → `["Pointeur"]`
- `Milieu` → `["Milieu"]`
- `Pointeur/Milieu` → `["Pointeur", "Milieu"]`

### Comment appliquer la migration

#### Méthode 1 : Via psql

```bash
psql -h <host> -U <user> -d <database> -f migrations/001_add_multiple_roles.sql
```

#### Méthode 2 : Via variable d'environnement DATABASE_URL

```bash
psql $DATABASE_URL -f migrations/001_add_multiple_roles.sql
```

#### Méthode 3 : Depuis Supabase Dashboard

1. Allez dans votre projet Supabase
2. Ouvrez l'éditeur SQL (SQL Editor)
3. Copiez le contenu de `001_add_multiple_roles.sql`
4. Exécutez le script

### Comment annuler la migration (rollback)

**⚠️ ATTENTION** : Le rollback peut entraîner une perte de données si des joueurs ont plusieurs rôles.

```bash
psql $DATABASE_URL -f migrations/001_rollback_multiple_roles.sql
```

### Vérification post-migration

Après avoir appliqué la migration, vous pouvez vérifier que tout s'est bien passé :

```sql
-- Voir la structure de la table
\d players

-- Voir les rôles de tous les joueurs
SELECT name, roles FROM players ORDER BY name;

-- Compter les joueurs par rôle
SELECT
    role_value,
    COUNT(DISTINCT name) as player_count
FROM players,
    jsonb_array_elements_text(roles) as role_value
GROUP BY role_value
ORDER BY role_value;
```

### Avantages de JSONB dans PostgreSQL

1. **Performance** : Index GIN pour recherches rapides
2. **Validation** : Contraintes et triggers pour garantir l'intégrité
3. **Flexibilité** : Requêtes SQL avancées avec les opérateurs JSONB (`@>`, `?`, etc.)

### Exemples de requêtes

```sql
-- Trouver tous les joueurs qui peuvent jouer Tireur
SELECT name, roles
FROM players
WHERE roles @> '["Tireur"]';

-- Trouver les joueurs qui peuvent jouer Pointeur OU Milieu
SELECT name, roles
FROM players
WHERE roles ?| ARRAY['Pointeur', 'Milieu'];

-- Trouver les joueurs polyvalents (plusieurs rôles)
SELECT name, roles, jsonb_array_length(roles) as role_count
FROM players
WHERE jsonb_array_length(roles) > 1;
```

## Notes importantes

- La migration est transactionnelle (BEGIN/COMMIT) : soit tout réussit, soit rien n'est modifié
- Un trigger valide automatiquement les rôles à l'insertion/mise à jour
- Les seuls rôles valides sont : `Tireur`, `Pointeur`, `Milieu`
- La colonne `roles` ne peut pas être vide (au moins un rôle requis)
