/// <reference path="../pb_data/types.d.ts" />

// Validation admin des comptes auto-inscrits : un joueur peut créer son compte
// (username + mot de passe) mais reste bloqué au login tant que `is_approved`
// est faux. `required: false` volontairement (même raison que les stats : un
// BoolField required rejette la valeur "vide"/false). Le défaut applicatif est
// géré côté backend (register → is_approved=false, admin/bootstrap → true).
migrate(
  (app) => {
    const collection = app.findCollectionByNameOrId("users")
    collection.fields.add(new BoolField({ name: "is_approved", required: false }))
    app.save(collection)

    // Backfill : tous les comptes existants sont de confiance (créés par l'admin
    // ou bootstrap) — sinon ils seraient verrouillés dès l'ajout du champ.
    const records = app.findAllRecords("users")
    for (const record of records) {
      record.set("is_approved", true)
      app.save(record)
    }
  },
  (app) => {
    const collection = app.findCollectionByNameOrId("users")
    collection.fields.removeByName("is_approved")
    app.save(collection)
  }
)
