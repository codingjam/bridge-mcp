"""Rate limiting key utilities."""


def build_rl_key(*, user_id: str, service_id: str, tool_name: str) -> str:
    """
    Build a composite key for rate limiting scope (user + service + tool).
    Format: rl:user:{user_id}|service:{service_id}|tool:{tool_name}
    - Normalize inputs: strip, lower service_id/tool_name
    - Replace '|' in any input with '_' to avoid delimiter collisions.
    - Return the composed key as a str.
    """
    # Normalize inputs: strip whitespace and replace '|' with '_' to avoid delimiter collisions
    normalized_user_id = user_id.strip().replace('|', '_')
    normalized_service_id = service_id.strip().lower().replace('|', '_')
    normalized_tool_name = tool_name.strip().lower().replace('|', '_')
    
    # Build the composite key
    return f"rl:user:{normalized_user_id}|service:{normalized_service_id}|tool:{normalized_tool_name}"
