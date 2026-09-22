def error_detail(code: str, message: str) -> dict[str, str]:
    """Build the `{code, message}` shape every route's HTTPException detail uses.

    Clients extract `code` for branching and `message` for display; both fields
    are required so neither side has to guess which shape a given endpoint uses.
    """
    return {"code": code, "message": message}
