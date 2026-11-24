"""
tools/bounty.py - Algora & GitHub Bounty Finder
Finds paid open source bounties and algorithmic challenges for Hermes to work on.
"""
from typing import Any, Optional
import httpx
from utils.helpers import logger


class BountyHunter:
    """Finds open bounties across GitHub and Algora ecosystems."""

    def __init__(self):
        self._http = httpx.AsyncClient(timeout=15.0)

    async def search_github_bounties(self, query: str = "bounty", limit: int = 5) -> list[dict[str, Any]]:
        """Search GitHub issues with bounty tags."""
        url = "https://api.github.com/search/issues"
        q = f"{query} label:bounty state:open is:issue"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Hermes-CoFounder-Agent",
        }

        try:
            r = await self._http.get(url, params={"q": q, "per_page": limit, "sort": "updated"}, headers=headers)
            if r.status_code == 200:
                data = r.json()
                items = []
                for item in data.get("items", []):
                    labels = [l["name"] for l in item.get("labels", [])]
                    items.append({
                        "title": item.get("title"),
                        "url": item.get("html_url"),
                        "repository": item.get("repository_url", "").replace("https://api.github.com/repos/", ""),
                        "labels": labels,
                        "created_at": item.get("created_at"),
                        "comments": item.get("comments"),
                    })
                return items
            else:
                logger.warning(f"[Bounty] GitHub API responded with status {r.status_code}")
                return []
        except Exception as e:
            logger.error(f"[Bounty] Error fetching bounties: {e}")
            return []

    async def get_summary_formatted(self, query: str = "python bounty") -> str:
        """Return human-readable markdown of open bounties."""
        results = await self.search_github_bounties(query=query, limit=5)
        if not results:
            return "Koi open bounties nahi mili abhi ke liye."

        lines = [f"🎯 **Open Bounties for '{query}':**\n"]
        for i, b in enumerate(results, 1):
            labels_str = ", ".join(b["labels"][:3])
            lines.append(f"{i}. **[{b['title']}]({b['url']})**")
            lines.append(f"   • Repo: `{b['repository']}` | Tags: `{labels_str}`")

        return "\n".join(lines)


bounty_hunter = BountyHunter()
