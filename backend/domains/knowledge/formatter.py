def format_entity_profile(entity: dict) -> str:
    if not entity:
        return "Entity not found."
    lines = [f"**{entity['name']}** ({entity['type']})"]
    for fact in entity.get("facts", []):
        lines.append(f"• {fact['content']}")
    return "\n".join(lines) if len(lines) > 1 else lines[0] + "\nNo facts recorded."


def format_search_results(results: list, query: str) -> str:
    if not results:
        return f"Nothing found for '{query}'."
    lines = [f"• {r['content']}" for r in results]
    return f"Results for '{query}':\n" + "\n".join(lines)
