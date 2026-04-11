# utils/pagination.py

from sqlalchemy import text

def paginate_query(db, select_query, base_query, where_clause="", params={}, page=1, limit=10, order_by=""):
    offset = (page - 1) * limit

    final_query = f"""
        {select_query}
        {base_query}
        {where_clause}
        {order_by}
        LIMIT :limit OFFSET :offset
    """

    final_params = {**params, "limit": limit, "offset": offset}

    result = db.execute(text(final_query), final_params)
    data = [dict(row._mapping) for row in result]

    count_query = f"""
        SELECT COUNT(*)
        {base_query}
        {where_clause}
    """

    total = db.execute(text(count_query), params).scalar()

    return {
        "data": data,
        "page": page,
        "limit": limit,
        "total": total
    }