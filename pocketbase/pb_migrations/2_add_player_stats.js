/// <reference path="../pb_data/types.d.ts" />

// Compteurs de statistiques par joueur — agrégés directement sur la collection
// "users" (pas d'historique par partie), incrémentés au fil des parties/manches
// par backend/api/stats.py. IMPORTANT : `required: false` volontairement — un
// NumberField required en PocketBase rejette la valeur 0 (traitée comme vide),
// ce qui bloquerait la création de tout nouveau joueur (0 partie au départ).
const STAT_FIELDS = [
  "games_played",
  "games_won",
  "games_lost",
  "capots_won",
  "generales_won",
  "contracts_taken",
  "contracts_made",
]

migrate(
  (app) => {
    const collection = app.findCollectionByNameOrId("users")
    for (const name of STAT_FIELDS) {
      collection.fields.add(
        new NumberField({ name, required: false, onlyInt: true, min: 0 })
      )
    }
    app.save(collection)
  },
  (app) => {
    const collection = app.findCollectionByNameOrId("users")
    for (const name of STAT_FIELDS) {
      collection.fields.removeByName(name)
    }
    app.save(collection)
  }
)
