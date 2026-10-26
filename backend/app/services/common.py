from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


def count_rows(db: Session, stmt: Select) -> int:
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    return db.execute(count_stmt).scalar_one()


def like_pattern(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def rate(numerator: int, denominator: int) -> float | None:
    if not denominator:
        return None
    return round(numerator * 100.0 / denominator, 1)
