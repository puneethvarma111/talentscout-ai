import os
from mcp.server.fastmcp import FastMCP
import httpx
from ddgs import DDGS
from dotenv import load_dotenv

load_dotenv()
mcp = FastMCP("TalentScout public candidate discovery")

@mcp.tool()
def github_search_users(query: str, per_page: int = 10) -> list[dict]:
    """Search public GitHub user profiles. Query can include location or skill terms."""
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = httpx.get(
        "https://api.github.com/search/users",
        params={"q": query, "per_page": min(max(per_page, 1), 20)},
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    items = response.json().get("items", [])
    results = []
    for item in items:
        login = item.get("login")
        profile = httpx.get(
            f"https://api.github.com/users/{login}",
            headers=headers,
            timeout=20,
        ).json()
        results.append({
            "name": profile.get("name") or login,
            "username": login,
            "profile_url": profile.get("html_url"),
            "bio": profile.get("bio"),
            "location": profile.get("location"),
            "company": profile.get("company"),
            "public_repos": profile.get("public_repos"),
            "followers": profile.get("followers"),
        })
    return results

@mcp.tool()
def public_web_search(query: str, max_results: int = 8) -> list[dict]:
    """Search publicly indexed web pages for portfolios and professional profiles."""
    rows = DDGS().text(query, max_results=min(max(max_results, 1), 10))
    return [
        {
            "title": row.get("title"),
            "url": row.get("href"),
            "snippet": row.get("body"),
        }
        for row in rows
    ]


@mcp.tool()
def github_list_user_repos(username: str, limit: int = 8) -> list[dict]:
    """List public repositories for a GitHub user as technical evidence."""
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = httpx.get(
        f"https://api.github.com/users/{username}/repos",
        params={"sort": "updated", "per_page": min(max(limit, 1), 15)},
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    return [
        {
            "name": repo.get("name"),
            "language": repo.get("language"),
            "stars": repo.get("stargazers_count", 0),
            "description": repo.get("description"),
            "url": repo.get("html_url"),
        }
        for repo in response.json()
    ]


if __name__ == "__main__":
    mcp.run()
