def choose_reported_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [row for row in rows if row["rank"] is not None]
