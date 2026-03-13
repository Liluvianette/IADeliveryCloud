"""
ingestion/git_ingest.py
GitHub API v3 — commits, pull requests, reviews, repo stats.

.env:
  GITHUB_TOKEN=ghp_xxxxxxxxxxxx

config.yml:
  git:
    enabled: true
    repos: []            # vacío = auto-descubrir repos del usuario
    lookback_days: 30
"""

import os, json, yaml, requests
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

CONFIG_PATH = Path(__file__).parent.parent / "config.yml"
OUTPUT_PATH = Path(__file__).parent.parent / "output"


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Cliente GitHub ────────────────────────────────────────

class GitHubClient:
    BASE = "https://api.github.com"

    def __init__(self, token):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept":        "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self._rate_remaining = 5000

    def get(self, endpoint, params=None):
        url  = f"{self.BASE}/{endpoint.lstrip('/')}"
        resp = requests.get(url, headers=self.headers, params=params, timeout=30)
        self._rate_remaining = int(resp.headers.get("X-RateLimit-Remaining", 5000))
        resp.raise_for_status()
        return resp.json()

    def get_paged(self, endpoint, params=None, max_pages=10):
        params    = {**(params or {}), "per_page": 100, "page": 1}
        all_items = []
        for page in range(1, max_pages + 1):
            params["page"] = page
            data = self.get(endpoint, params)
            if not isinstance(data, list) or not data:
                break
            all_items.extend(data)
            if len(data) < 100:
                break
        return all_items

    def verify_auth(self):
        data = self.get("user")
        print(f"  → Autenticado como: {data.get('login')} ({data.get('name', '')})")
        return data

    def get_user_repos(self):
        return self.get_paged("user/repos", {
            "sort": "pushed", "direction": "desc",
            "affiliation": "owner,collaborator,organization_member"
        })

    def get_commits(self, repo, since_date):
        try:
            return self.get_paged(f"repos/{repo}/commits",
                                  {"since": f"{since_date}T00:00:00Z"})
        except requests.HTTPError as e:
            if e.response.status_code in (409, 404):
                return []
            raise

    def get_pulls(self, repo, state="all"):
        return self.get_paged(f"repos/{repo}/pulls",
                              {"state": state, "sort": "updated", "direction": "desc"})

    def get_pull_reviews(self, repo, pull_number):
        try:
            result = self.get(f"repos/{repo}/pulls/{pull_number}/reviews")
            return result if isinstance(result, list) else []
        except Exception:
            return []


# ── Normalización ─────────────────────────────────────────

def normalize_commit(raw, repo):
    commit  = raw.get("commit", {})
    author  = commit.get("author", {})
    gh_auth = raw.get("author") or {}
    return {
        "sha":      raw.get("sha", "")[:8],
        "repo":     repo.split("/")[-1],
        "repo_full":repo,
        "author":   author.get("name", ""),
        "email":    author.get("email", ""),
        "login":    gh_auth.get("login", ""),
        "date":     (author.get("date") or "")[:10],
        "message":  commit.get("message", "").split("\n")[0][:100],
    }


def _parse_jira_keys(text):
    """Extrae claves Jira (ej. CDIP-123) de un texto."""
    import re
    if not text:
        return []
    return list(set(re.findall(r"[A-Z][A-Z0-9]+-\d+", text)))


def _calc_lead_time_hours(created_at, merged_at):
    """Calcula horas desde creación del PR hasta merge."""
    if not created_at or not merged_at:
        return None
    try:
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        created = datetime.strptime(created_at, fmt)
        merged = datetime.strptime(merged_at, fmt)
        delta = (merged - created).total_seconds() / 3600
        return round(delta, 1)
    except (ValueError, TypeError):
        return None


def normalize_pull(raw, repo):
    user   = raw.get("user") or {}
    merged = raw.get("merged_at")
    head   = raw.get("head") or {}
    title  = raw.get("title", "")
    branch = head.get("ref", "")

    jira_keys = _parse_jira_keys(title) + _parse_jira_keys(branch)
    jira_keys = list(set(jira_keys))

    lead_time = _calc_lead_time_hours(raw.get("created_at"), merged)

    return {
        "number":      raw.get("number"),
        "repo":        repo.split("/")[-1],
        "repo_full":   repo,
        "title":       title[:100],
        "state":       raw.get("state", ""),
        "merged":      merged is not None,
        "author":      user.get("login", ""),
        "created_at":  (raw.get("created_at") or "")[:10],
        "updated_at":  (raw.get("updated_at") or "")[:10],
        "merged_at":   (merged or "")[:10] or None,
        "base_branch": (raw.get("base") or {}).get("ref", ""),
        "additions":   raw.get("additions", 0),
        "deletions":   raw.get("deletions", 0),
        "changed_files": raw.get("changed_files", 0),
        "comments":    raw.get("comments", 0),
        "review_comments": raw.get("review_comments", 0),
        "lead_time_hours": lead_time,
        "jira_keys":   jira_keys,
    }


def normalize_review(raw, repo, pull_number):
    user = raw.get("user") or {}
    return {
        "pull_number":  pull_number,
        "repo":         repo.split("/")[-1],
        "reviewer":     user.get("login", ""),
        "state":        raw.get("state", ""),
        "submitted_at": (raw.get("submitted_at") or "")[:10],
    }


# ── Métricas ──────────────────────────────────────────────

def compute_metrics(commits, pulls, reviews):
    by_author = defaultdict(lambda: {
        "commits": 0, "prs_opened": 0, "prs_merged": 0,
        "reviews_given": 0, "approvals": 0, "changes_requested": 0,
        "repos": set(), "recent_commits": [],
    })
    by_repo = defaultdict(lambda: {"commits": 0, "prs": 0, "merged_prs": 0, "authors": set()})

    for c in commits:
        key = c["login"] or c["email"]
        if not key:
            continue
        by_author[key]["commits"] += 1
        by_author[key]["repos"].add(c["repo"])
        if len(by_author[key]["recent_commits"]) < 5:
            by_author[key]["recent_commits"].append({"date": c["date"], "message": c["message"], "repo": c["repo"]})
        by_repo[c["repo"]]["commits"] += 1
        by_repo[c["repo"]]["authors"].add(key)

    for p in pulls:
        key = p["author"]
        if not key: continue
        by_author[key]["prs_opened"] += 1
        if p["merged"]:
            by_author[key]["prs_merged"] += 1
        by_repo[p["repo"]]["prs"] += 1
        if p["merged"]:
            by_repo[p["repo"]]["merged_prs"] += 1

    for r in reviews:
        key = r["reviewer"]
        if not key: continue
        by_author[key]["reviews_given"] += 1
        if r["state"] == "APPROVED":
            by_author[key]["approvals"] += 1
        elif r["state"] == "CHANGES_REQUESTED":
            by_author[key]["changes_requested"] += 1

    return {
        "by_author": {k: {**v, "repos": list(v["repos"])} for k, v in by_author.items()},
        "by_repo":   {k: {**v, "authors": list(v["authors"])} for k, v in by_repo.items()},
        "totals": {
            "commits":        len(commits),
            "pulls":          len(pulls),
            "merged_prs":     sum(1 for p in pulls if p["merged"]),
            "reviews":        len(reviews),
            "active_authors": len(by_author),
            "active_repos":   len(by_repo),
        },
    }


# ── Modo real ─────────────────────────────────────────────

def fetch_from_github(config):
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        raise ValueError(
            "Falta GITHUB_TOKEN en .env\n"
            "  → Genera uno en: https://github.com/settings/tokens\n"
            "  → Permisos: repo (read), workflow"
        )

    client     = GitHubClient(token)
    user_info  = client.verify_auth()
    username   = user_info.get("login", "")
    lookback   = int(config["git"].get("lookback_days", 30))
    since_date = (datetime.utcnow() - timedelta(days=lookback)).strftime("%Y-%m-%d")
    repo_list  = list(config["git"].get("repos", []))

    if not repo_list:
        print("  → Descubriendo repos con actividad reciente...")
        raw_repos = client.get_user_repos()
        repo_list = [
            r["full_name"] for r in raw_repos
            if (r.get("pushed_at") or "") >= since_date
            and not r.get("archived", False)
        ]
        print(f"  → {len(repo_list)} repos: {repo_list[:5]}{'...' if len(repo_list)>5 else ''}")

    if not repo_list:
        print("  → Sin repos con actividad reciente")
        return {"source":"github_real","username":username,"repos":[],"commits":[],"pulls":[],"reviews":[],"metrics":compute_metrics([],[],[])}

    all_commits, all_pulls, all_reviews = [], [], []

    for repo in repo_list:
        print(f"  → {repo}: ", end="", flush=True)

        commits = [normalize_commit(c, repo) for c in client.get_commits(repo, since_date)]
        all_commits.extend(commits)
        print(f"{len(commits)} commits", end="  ", flush=True)

        raw_pulls = client.get_pulls(repo, state="all")
        # Filtrar por fecha
        raw_pulls = [p for p in raw_pulls if (p.get("updated_at") or "") >= since_date]
        pulls     = [normalize_pull(p, repo) for p in raw_pulls]
        all_pulls.extend(pulls)
        print(f"{len(pulls)} PRs", end="  ", flush=True)

        reviews_count = 0
        for pull in raw_pulls[:15]:  # máx 15 PRs para conservar rate limit
            for r in client.get_pull_reviews(repo, pull["number"]):
                all_reviews.append(normalize_review(r, repo, pull["number"]))
                reviews_count += 1
        print(f"{reviews_count} reviews", flush=True)

        if client._rate_remaining < 100:
            print(f"  ⚠️  Rate limit bajo ({client._rate_remaining} restantes) — deteniendo")
            break

    return {
        "source":        "github_real",
        "username":      username,
        "repos":         repo_list,
        "lookback_days": lookback,
        "commits":       all_commits,
        "pulls":         all_pulls,
        "reviews":       all_reviews,
        "metrics":       compute_metrics(all_commits, all_pulls, all_reviews),
    }


# ── Modo mock ─────────────────────────────────────────────

def generate_mock_data():
    today = datetime.utcnow()
    def d(days): return (today - timedelta(days=days)).strftime("%Y-%m-%d")

    import random; random.seed(42)
    repos   = ["infra-eks-platform","helm-charts-core","github-actions-templates","security-policies"]
    authors = [("amartinez","Alejandro Martínez","amartinez@empresa.com"),
               ("cvalencia","Carolina Valencia","cvalencia@empresa.com"),
               ("romena","Roberto Omena","romena@empresa.com"),
               ("lcastro","Lucía Castro","lcastro@empresa.com"),
               ("dquiroga","Diego Quiroga","dquiroga@empresa.com")]
    messages = ["feat: add cluster autoscaler config","fix: node group taints corrected",
                "chore: update terraform provider versions","feat: implement spot instance support",
                "fix: RBAC permissions for monitoring namespace","feat: add Prometheus alert rules",
                "fix: ingress annotations for ALB","chore: bump chart versions",
                "feat: Python pipeline template v1","feat: add SAST scan step",
                "fix: cache key collision on matrix builds","feat: WAF managed rules - OWASP core",
                "docs: add compliance mapping NIST-800","refactor: split IAM policies by service",
                "feat: add Grafana dashboard for EKS"]

    commits = [{"sha":f"{a[0][:2]}{random.randint(0,9999):04x}","repo":random.choice(repos),
                "repo_full":f"org/{random.choice(repos)}","author":a[1],"email":a[2],"login":a[0],
                "date":d(random.randint(0,29)),"message":random.choice(messages)}
               for _ in range(55) for a in [random.choice(authors)]]

    pulls = [{"number":i+1,"repo":random.choice(repos),"repo_full":"org/repo",
              "title":random.choice(messages)[:60],"state":"closed" if random.random()>0.3 else "open",
              "merged":random.random()>0.3,"author":random.choice(authors)[0],
              "created_at":d(random.randint(2,28)),"updated_at":d(1),"merged_at":d(1) if random.random()>0.3 else None,
              "base_branch":"main","additions":random.randint(10,300),"deletions":random.randint(5,100),
              "changed_files":random.randint(1,15),"comments":random.randint(0,5),"review_comments":random.randint(0,8)}
             for i in range(12)]

    review_states = ["APPROVED","APPROVED","CHANGES_REQUESTED","COMMENTED"]
    reviews = [{"pull_number":p["number"],"repo":p["repo"],
                "reviewer":random.choice([a[0] for a in authors if a[0]!=p["author"]]),
                "state":random.choice(review_states),"submitted_at":p["created_at"]}
               for p in pulls]

    return {"source":"mock","username":"mock_user","repos":repos,
            "commits":commits,"pulls":pulls,"reviews":reviews,
            "metrics":compute_metrics(commits,pulls,reviews)}


# ── Runner ────────────────────────────────────────────────

def run():
    print("📥 Ingesta Git...")
    config = load_config()

    if config["git"]["enabled"]:
        print("  → Modo: GitHub API real")
        try:
            data = fetch_from_github(config)
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
            print("  → Fallback a datos mock")
            data = generate_mock_data()
    else:
        print("  → Modo: datos simulados (git.enabled = false)")
        data = generate_mock_data()

    data["generated_at"] = datetime.utcnow().isoformat()
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_PATH / "git_data.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    t = data["metrics"]["totals"]
    print(f"  ✅ {t['commits']} commits | {t['pulls']} PRs ({t['merged_prs']} merged) | "
          f"{t['reviews']} reviews | {t['active_authors']} autores → {out_file}")
    return data


if __name__ == "__main__":
    run()