import sqlite3

DB_PATH = "toysrus.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crea la tabla de juguetes si no existe."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS toys (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            price       REAL NOT NULL,
            category    TEXT,
            age_range   TEXT,
            brand       TEXT,
            url         TEXT,
            image_url   TEXT
        );
    """)

    conn.commit()
    conn.close()


def insert_toy(toy):
    """
    Inserta un juguete si no existe ya uno con el mismo nombre y precio.
    """
    name = toy.get("name")
    price = toy.get("price")

    if name is None or price is None:
        return  # datos incompletos, no insertamos

    # Evitamos duplicados simples por nombre + precio
    if toy_exists(name, price):
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO toys (name, price, category, age_range, brand, url, image_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        price,
        toy.get("category"),
        toy.get("age_range"),
        toy.get("brand"),
        toy.get("url"),
        toy.get("image_url"),
    ))
    conn.commit()
    conn.close()


def get_distinct_values(field):
    """Devuelve valores únicos de una columna (para rellenar selects)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"SELECT DISTINCT {field} FROM toys "
        f"WHERE {field} IS NOT NULL AND {field} <> '' "
        f"ORDER BY {field}"
    )
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows


def search_toys(category=None, age_range=None, brand=None,
                min_price=None, max_price=None, order_by="price_asc"):
    """
    Busca juguetes aplicando filtros y ordenando.

    order_by puede ser:
        - price_asc
        - price_desc
        - name_asc
        - name_desc
    """
    conn = get_connection()
    cur = conn.cursor()

    query = "SELECT * FROM toys WHERE 1=1"
    params = []

    if category:
        query += " AND category = ?"
        params.append(category)

    if age_range:
        query += " AND age_range = ?"
        params.append(age_range)

    if brand:
        query += " AND brand = ?"
        params.append(brand)

    if min_price is not None:
        query += " AND price >= ?"
        params.append(min_price)

    if max_price is not None:
        query += " AND price <= ?"
        params.append(max_price)

    order_map = {
        "price_asc": "price ASC",
        "price_desc": "price DESC",
        "name_asc": "name ASC",
        "name_desc": "name DESC"
    }
    order_clause = order_map.get(order_by, "price ASC")
    query += f" ORDER BY {order_clause}"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_all_toys():
    """
    Devuelve todos los juguetes de la BBDD.
    La usaremos para la búsqueda 'IA' por similitud de texto.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM toys")
    rows = cur.fetchall()
    conn.close()
    return rows
def toy_exists(name, price):
    """
    Devuelve True si ya hay un juguete con ese nombre y precio.
    Es una forma sencilla de evitar duplicados.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM toys WHERE name = ? AND price = ? LIMIT 1",
        (name, price)
    )
    row = cur.fetchone()
    conn.close()
    return row is not None
