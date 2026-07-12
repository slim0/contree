"""Client HTTP minimal vers l'API REST de PocketBase.

Le backend s'authentifie en tant que superuser PocketBase (compte de service,
distinct des comptes métier de l'app) pour gérer la collection "users" —
aucune règle d'API n'est ouverte au public (voir pocketbase/pb_migrations).
"""

import os

import httpx

PB_URL = os.getenv("PB_URL", "http://localhost:8090")
PB_SUPERUSER_EMAIL = os.getenv("PB_SUPERUSER_EMAIL", "")
PB_SUPERUSER_PASSWORD = os.getenv("PB_SUPERUSER_PASSWORD", "")

_USERS_COLLECTION = "users"


class PocketBaseError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"PocketBase error {status_code}: {detail}")


def _escape_filter_value(value: str) -> str:
    """Échappe une valeur pour l'interpoler dans un filtre PocketBase.

    PocketBase n'expose pas de binding de paramètres via l'API REST brute
    (seuls les SDKs officiels le font côté client) — on échappe donc
    manuellement antislash puis guillemet simple pour éviter toute injection
    dans l'expression de filtre.
    """
    return value.replace("\\", "\\\\").replace("'", "\\'")


class PocketBaseClient:
    def __init__(
        self,
        base_url: str = PB_URL,
        superuser_email: str = PB_SUPERUSER_EMAIL,
        superuser_password: str = PB_SUPERUSER_PASSWORD,
    ) -> None:
        self._superuser_email = superuser_email
        self._superuser_password = superuser_password
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=10.0)
        self._token: str | None = None

    def _authenticate(self) -> str:
        r = self._client.post(
            "/api/collections/_superusers/auth-with-password",
            json={
                "identity": self._superuser_email,
                "password": self._superuser_password,
            },
        )
        if r.is_error:
            raise PocketBaseError(r.status_code, r.text)
        token = r.json()["token"]
        self._token = token
        return token

    def _authed_request(self, method: str, path: str, **kwargs) -> httpx.Response:
        token = self._token or self._authenticate()
        r = self._client.request(
            method, path, headers={"Authorization": f"Bearer {token}"}, **kwargs
        )
        if r.status_code == 401:
            token = self._authenticate()
            r = self._client.request(
                method, path, headers={"Authorization": f"Bearer {token}"}, **kwargs
            )
        return r

    def get_by_id(self, user_id: str) -> dict | None:
        r = self._authed_request(
            "GET", f"/api/collections/{_USERS_COLLECTION}/records/{user_id}"
        )
        if r.status_code == 404:
            return None
        if r.is_error:
            raise PocketBaseError(r.status_code, r.text)
        return r.json()

    def get_by_username(self, username: str) -> dict | None:
        r = self._authed_request(
            "GET",
            f"/api/collections/{_USERS_COLLECTION}/records",
            params={
                "filter": f"username='{_escape_filter_value(username)}'",
                "perPage": 1,
            },
        )
        if r.is_error:
            raise PocketBaseError(r.status_code, r.text)
        items = r.json()["items"]
        return items[0] if items else None

    def list_all(self) -> list[dict]:
        r = self._authed_request(
            "GET",
            f"/api/collections/{_USERS_COLLECTION}/records",
            params={"sort": "created", "perPage": 500},
        )
        if r.is_error:
            raise PocketBaseError(r.status_code, r.text)
        return r.json()["items"]

    def count(self) -> int:
        r = self._authed_request(
            "GET",
            f"/api/collections/{_USERS_COLLECTION}/records",
            params={"perPage": 1},
        )
        if r.is_error:
            raise PocketBaseError(r.status_code, r.text)
        return r.json()["totalItems"]

    def create(
        self,
        username: str,
        password: str,
        is_admin: bool = False,
        must_change_password: bool = True,
    ) -> dict:
        r = self._authed_request(
            "POST",
            f"/api/collections/{_USERS_COLLECTION}/records",
            json={
                "username": username,
                "password": password,
                "passwordConfirm": password,
                "is_admin": is_admin,
                "must_change_password": must_change_password,
            },
        )
        if r.is_error:
            raise PocketBaseError(r.status_code, r.text)
        return r.json()

    def set_password(self, user_id: str, password: str) -> dict:
        r = self._authed_request(
            "PATCH",
            f"/api/collections/{_USERS_COLLECTION}/records/{user_id}",
            json={
                "password": password,
                "passwordConfirm": password,
                "must_change_password": False,
            },
        )
        if r.is_error:
            raise PocketBaseError(r.status_code, r.text)
        return r.json()

    def verify_credentials(self, username: str, password: str) -> dict | None:
        """Authentifie via PocketBase (identity/password) — délègue le hachage/vérification."""
        r = self._client.post(
            f"/api/collections/{_USERS_COLLECTION}/auth-with-password",
            json={"identity": username, "password": password},
        )
        if r.status_code != 200:
            return None
        return r.json()["record"]

    def delete(self, user_id: str) -> None:
        r = self._authed_request(
            "DELETE", f"/api/collections/{_USERS_COLLECTION}/records/{user_id}"
        )
        if r.is_error:
            raise PocketBaseError(r.status_code, r.text)


_client: PocketBaseClient | None = None


def get_pb_client() -> PocketBaseClient:
    global _client
    if _client is None:
        _client = PocketBaseClient()
    return _client
