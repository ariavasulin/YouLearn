"""You.com Search API tools for Agno agents."""

from __future__ import annotations

import json
import os

import httpx
from agno.tools import Toolkit

_API_URL = "https://ydc-index.io/v1/search"


class YouComSearchTools(Toolkit):
    """Search the web using You.com API for fact-checking and research."""

    def __init__(
        self,
        api_key: str | None = None,
        num_results: int = 5,
    ):
        self.api_key = api_key or os.getenv("YOULEARN_YOU_API_KEY", "")
        self.num_results = num_results
        super().__init__(
            name="you_com_search",
            tools=[self.search_web],
            async_tools=[(self.asearch_web, "search_web")],
        )

    def _slim_results(self, data: dict) -> str:
        """Extract essential fields from You.com response."""
        results = []
        for hit in data.get("results", {}).get("web", []):
            results.append({
                "title": hit.get("title", ""),
                "url": hit.get("url", ""),
                "snippets": hit.get("snippets", [])[:2],
            })
        return json.dumps(results, indent=2)

    def search_web(self, query: str) -> str:
        """Search the web to verify a factual claim or research a topic.

        Use this to fact-check historical dates, theorem attributions,
        named mathematical concepts, and other verifiable claims.

        Args:
            query: A specific search query to verify a claim.
                   Good: "When did Hermite prove e is transcendental"
                   Good: "Who proved the Heine-Borel theorem"
                   Bad: "math stuff"

        Returns:
            JSON string with search results including titles, URLs,
            and text snippets from web sources.
        """
        resp = httpx.get(
            _API_URL,
            params={"query": query, "count": self.num_results},
            headers={"X-API-Key": self.api_key},
            timeout=30.0,
        )
        resp.raise_for_status()
        return self._slim_results(resp.json())

    async def asearch_web(self, query: str) -> str:
        """Async version of search_web."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                _API_URL,
                params={"query": query, "count": self.num_results},
                headers={"X-API-Key": self.api_key},
            )
            resp.raise_for_status()
            return self._slim_results(resp.json())
