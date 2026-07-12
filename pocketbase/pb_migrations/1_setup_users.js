/// <reference path="../pb_data/types.d.ts" />

// Adapte la collection "users" intégrée de PocketBase pour l'app Belote Contrée :
// login par username (pas d'email), champs métier is_admin / must_change_password,
// et gestion exclusivement par le superuser (aucune inscription publique).
migrate(
  (app) => {
    const collection = app.findCollectionByNameOrId("users")

    collection.fields.add(
      new TextField({
        name: "username",
        required: true,
      })
    )
    collection.fields.add(
      new BoolField({
        name: "is_admin",
        required: false,
      })
    )
    collection.fields.add(
      new BoolField({
        name: "must_change_password",
        required: false,
      })
    )

    const emailField = collection.fields.getByName("email")
    emailField.required = false

    collection.indexes.push(
      "CREATE UNIQUE INDEX idx_users_username ON users (username)"
    )

    collection.passwordAuth.identityFields = ["username", "email"]

    collection.listRule = null
    collection.viewRule = null
    collection.createRule = null
    collection.updateRule = null
    collection.deleteRule = null

    app.save(collection)
  },
  (app) => {
    const collection = app.findCollectionByNameOrId("users")
    collection.fields.removeByName("is_admin")
    collection.fields.removeByName("must_change_password")
    collection.fields.removeByName("username")
    app.save(collection)
  }
)
