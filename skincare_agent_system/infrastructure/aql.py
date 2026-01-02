"""
Agent Query Language (AQL)
Standardized query interface for agents to access data without rigid getters.
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class AgentQuery(BaseModel):
    """
    Standard AQL Query Structure.
    "Give me [select] from [data_source] where [filters]"
    """

    select: List[str] = Field(..., description="Fields to retrieve")
    from_source: str = Field(..., description="Data source (e.g., 'product', 'memory')")
    where: Optional[Dict[str, Any]] = Field(
        None, description="Filter criteria (equality)"
    )
    limit: Optional[int] = Field(None, description="Max items to return")


class QueryProcessor:
    """
    Executes AQL queries against data sources.
    """

    @staticmethod
    def execute(
        query: AgentQuery, context_data: Dict[str, Any]
    ) -> Union[Dict[str, Any], List[Any]]:
        """
        Execute query against context data.

        Args:
            query: Parsed AgentQuery
            context_data: Dictionary containing data sources (e.g. {'product': {...}})

        Returns:
            Result set (dict or list)
        """
        source_data = context_data.get(query.from_source)

        if not source_data:
            return {"error": f"Source '{query.from_source}' not found"}

        # Normalize source to list for filtering
        items = source_data if isinstance(source_data, list) else [source_data]

        # 1. Filter (WHERE)
        filtered_items = []
        if query.where:
            for item in items:
                match = True
                for key, val in query.where.items():
                    # Support dotted access for nested keys could be added here
                    if item.get(key) != val:
                        match = False
                        break
                if match:
                    filtered_items.append(item)
        else:
            filtered_items = items

        # 2. Limit
        if query.limit:
            filtered_items = filtered_items[: query.limit]

        # 3. Select (Project)
        results = []
        for item in filtered_items:
            if "*" in query.select:
                projected = item
            else:
                projected = {k: item.get(k) for k in query.select if k in item}
            results.append(projected)

        # If original source was dict (single item) and we have 1 result, return dict
        if isinstance(source_data, dict) and len(results) == 1:
            return results[0]

        return results
