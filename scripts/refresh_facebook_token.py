"""Keep the Facebook Page token alive forever and persist it to the repo secret.

Runs in GitHub Actions (which can reach graph.facebook.com). A Page access
token *derived from a long-lived User token never expires* -- so this re-derives
it on a schedule and writes it back, guaranteeing the schedule never breaks
even if a short-lived token was pasted by mistake.

Each run:
  1. Exchanges the stored User token for a fresh long-lived (60-day) User token.
  2. Uses it to fetch the Page's access token (permanent) for FACEBOOK_PAGE_ID.
  3. Writes FACEBOOK_PAGE_ACCESS_TOKEN and the refreshed FACEBOOK_USER_TOKEN
     back to the repository secrets (encrypted with the repo public key).

Env vars:
  FACEBOOK_APP_ID, FACEBOOK_APP_SECRET   the Meta app credentials
  FACEBOOK_PAGE_ID                       the Page whose token we refresh
  FACEBOOK_USER_TOKEN                    a (long-lived) User token to derive from
  GH_PAT                                 fine-grained PAT with Secrets: write
  GITHUB_REPOSITORY                      owner/repo (set by Actions)

Tokens are never printed.
"""

import base64
import os
import sys

import requests

GRAPH = "https://graph.facebook.com/v21.0"
GITHUB = "https://api.github.com"


def long_lived_user_token(app_id: str, app_secret: str, token: str):
    r = requests.get(
        f"{GRAPH}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": token,
        },
        timeout=30,
    ).json()
    return r.get("access_token"), r.get("error")


def page_token(page_id: str, user_token: str):
    r = requests.get(
        f"{GRAPH}/{page_id}",
        params={"fields": "access_token,name", "access_token": user_token},
        timeout=30,
    ).json()
    return r.get("access_token"), r.get("name"), r.get("error")


def update_secret(repo: str, pat: str, name: str, value: str) -> None:
    from nacl import encoding, public

    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    key = requests.get(
        f"{GITHUB}/repos/{repo}/actions/secrets/public-key", headers=headers, timeout=30
    )
    key.raise_for_status()
    key = key.json()

    pub = public.PublicKey(key["key"].encode(), encoding.Base64Encoder())
    sealed = public.SealedBox(pub).encrypt(value.encode())
    encrypted = base64.b64encode(sealed).decode()

    resp = requests.put(
        f"{GITHUB}/repos/{repo}/actions/secrets/{name}",
        headers=headers,
        json={"encrypted_value": encrypted, "key_id": key["key_id"]},
        timeout=30,
    )
    resp.raise_for_status()


def main() -> int:
    app_id = os.environ.get("FACEBOOK_APP_ID", "").strip()
    app_secret = os.environ.get("FACEBOOK_APP_SECRET", "").strip()
    page_id = os.environ.get("FACEBOOK_PAGE_ID", "").strip()
    user_token = os.environ.get("FACEBOOK_USER_TOKEN", "").strip()
    pat = os.environ.get("GH_PAT", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()

    if not (app_id and app_secret and page_id and user_token):
        print("Facebook auto-refresh not configured (need FACEBOOK_APP_ID, "
              "FACEBOOK_APP_SECRET, FACEBOOK_PAGE_ID, FACEBOOK_USER_TOKEN). Skipping.",
              file=sys.stderr)
        return 0

    # Step 1: refresh the long-lived user token (kept valid as it is used).
    llt, err = long_lived_user_token(app_id, app_secret, user_token)
    if not llt:
        msg = err.get("message") if isinstance(err, dict) else err
        print(f"Could not refresh the user token: {msg}. Using the existing one.",
              file=sys.stderr)
        llt = user_token

    # Step 2: derive the (permanent) Page token from it.
    ptoken, name, err = page_token(page_id, llt)
    if not ptoken:
        msg = err.get("message") if isinstance(err, dict) else err
        print(f"Could not fetch the Page token: {msg}. Regenerate the user token "
              "in the dashboard's Guided setup (Facebook step).", file=sys.stderr)
        return 1
    print(f"Derived a permanent Page token for '{name or page_id}'.")

    if not (pat and repo):
        print("GH_PAT or GITHUB_REPOSITORY missing -- cannot persist the token.",
              file=sys.stderr)
        return 1

    update_secret(repo, pat, "FACEBOOK_PAGE_ACCESS_TOKEN", ptoken)
    update_secret(repo, pat, "FACEBOOK_USER_TOKEN", llt)
    print("Updated FACEBOOK_PAGE_ACCESS_TOKEN and FACEBOOK_USER_TOKEN secrets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
