from datetime import datetime
from database.db import get_db


def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    conn = get_db()
    sql = (
        "SELECT date, description, category, amount FROM expenses "
        "WHERE user_id = ?"
    )
    params = [user_id]
    if date_from and date_to:
        sql += " AND date BETWEEN ? AND ?"
        params.extend([date_from, date_to])
    sql += " ORDER BY date DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [
        {
            "date": datetime.strptime(r["date"], "%Y-%m-%d").strftime("%b %-d"),
            "description": r["description"],
            "category": r["category"],
            "amount": f"₹{r['amount']:.2f}",
        }
        for r in rows
    ]


def get_summary_stats(user_id, date_from=None, date_to=None):
    conn = get_db()
    base = "FROM expenses WHERE user_id = ?"
    params = [user_id]
    if date_from and date_to:
        base += " AND date BETWEEN ? AND ?"
        params.extend([date_from, date_to])
    row = conn.execute(f"SELECT SUM(amount), COUNT(*) {base}", params).fetchone()
    top = conn.execute(
        f"SELECT category {base} GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
        params
    ).fetchone()
    total = row[0] or 0.0
    count = row[1] or 0
    conn.close()
    return {
        "total_spent": f"₹{total:.2f}",
        "transaction_count": count,
        "top_category": top["category"] if top else "—",
    }


def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    dt = datetime.strptime(row["created_at"][:10], "%Y-%m-%d")
    initials = "".join(w[0].upper() for w in row["name"].split()[:2])
    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": dt.strftime("%B %Y"),
        "initials": initials,
    }


def get_category_breakdown(user_id, date_from=None, date_to=None):
    conn = get_db()
    sql = (
        "SELECT category, SUM(amount) as total FROM expenses "
        "WHERE user_id = ?"
    )
    params = [user_id]
    if date_from and date_to:
        sql += " AND date BETWEEN ? AND ?"
        params.extend([date_from, date_to])
    sql += " GROUP BY category ORDER BY total DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    if not rows:
        return []
    grand = sum(r["total"] for r in rows)
    result = [
        {
            "name": r["category"],
            "amount": f"₹{r['total']:.2f}",
            "pct": round(r["total"] / grand * 100),
        }
        for r in rows
    ]
    diff = 100 - sum(c["pct"] for c in result)
    result[0]["pct"] += diff
    return result
