"""
analysis/identity_resolver.py
Resuelve identidades entre Jira, GitHub y team.yml.

Mapea usuarios de Jira (displayName/email) y GitHub (login/email)
a member_id del equipo definido en team.yml.
"""

import json
from difflib import SequenceMatcher
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent.parent / "output"

_resolver = None


class IdentityResolver:
    def __init__(self, team: list[dict]):
        self._by_jira_email = {}
        self._by_jira_name = {}
        self._by_github_login = {}
        self._by_github_email = {}
        self._by_email = {}
        self._names = {}
        self._unresolved = []

        for m in team:
            mid = m["id"]
            self._by_email[m.get("email", "").lower()] = mid
            self._names[mid] = m["name"]

            ids = m.get("identities", {})
            if ids.get("jira_email"):
                self._by_jira_email[ids["jira_email"].lower()] = mid
            if ids.get("jira_display_name"):
                self._by_jira_name[ids["jira_display_name"].lower()] = mid
            if ids.get("github_login"):
                self._by_github_login[ids["github_login"].lower()] = mid
            for ge in ids.get("github_emails", []):
                self._by_github_email[ge.lower()] = mid

    def resolve_jira(self, assignee_name: str = None, assignee_email: str = None) -> str | None:
        """Resuelve un usuario de Jira a member_id."""
        if assignee_email:
            email_lower = assignee_email.lower()
            if email_lower in self._by_jira_email:
                return self._by_jira_email[email_lower]
            if email_lower in self._by_email:
                return self._by_email[email_lower]

        if assignee_name:
            name_lower = assignee_name.lower()
            if name_lower in self._by_jira_name:
                return self._by_jira_name[name_lower]
            # Fuzzy match
            best_match = self._fuzzy_match_name(assignee_name)
            if best_match:
                return best_match

        key = assignee_email or assignee_name or "unknown"
        if key not in self._unresolved:
            self._unresolved.append(key)
        return None

    def resolve_github(self, login: str = None, email: str = None) -> str | None:
        """Resuelve un usuario de GitHub a member_id."""
        if login:
            login_lower = login.lower()
            if login_lower in self._by_github_login:
                return self._by_github_login[login_lower]

        if email:
            email_lower = email.lower()
            if email_lower in self._by_github_email:
                return self._by_github_email[email_lower]
            if email_lower in self._by_jira_email:
                return self._by_jira_email[email_lower]
            if email_lower in self._by_email:
                return self._by_email[email_lower]

        key = login or email or "unknown"
        if key not in self._unresolved:
            self._unresolved.append(key)
        return None

    def _fuzzy_match_name(self, name: str, threshold: float = 0.75) -> str | None:
        """Busca coincidencia aproximada por nombre."""
        best_score = 0.0
        best_id = None
        for mid, member_name in self._names.items():
            score = SequenceMatcher(None, name.lower(), member_name.lower()).ratio()
            if score > best_score and score >= threshold:
                best_score = score
                best_id = mid
        return best_id

    def get_unresolved(self) -> list[str]:
        return self._unresolved.copy()

    def get_member_name(self, member_id: str) -> str:
        return self._names.get(member_id, member_id)


def load_resolver() -> IdentityResolver:
    """Carga el resolver desde team_raw.json."""
    global _resolver
    if _resolver is not None:
        return _resolver

    team_file = OUTPUT_PATH / "team_raw.json"
    with open(team_file, encoding="utf-8") as f:
        team = json.load(f)["team"]

    _resolver = IdentityResolver(team)
    return _resolver


def run() -> IdentityResolver:
    """Inicializa y retorna el resolver, reportando identidades no resueltas."""
    print("🔗 Inicializando resolución de identidades...")
    resolver = load_resolver()
    print(f"  ✅ Identity resolver listo — {len(resolver._names)} miembros mapeados")
    return resolver


if __name__ == "__main__":
    run()
