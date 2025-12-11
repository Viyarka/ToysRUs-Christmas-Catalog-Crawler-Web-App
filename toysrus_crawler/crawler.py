import re
import time
import requests
from bs4 import BeautifulSoup

from db import init_db, insert_toy

# ----------------------------------------
# CONFIG: múltiples páginas/categorías
# ----------------------------------------

# Cada tupla: (nombre_categoria_que_guardamos, URL_de_listado)
CATEGORY_PAGES = [
    ("Juguetes (general)", "https://www.toysrus.es/Juguetes/c/juguetes"),
    ("Arte y Manualidades", "https://www.toysrus.es/Arte-y-Manualidades/c/Juguetes-Categorias-ArteManualidades"),
    ("Juegos y Puzzles", "https://www.toysrus.es/Juegos-y-Puzzles/c/Juegos_y_Puzzles"),
    ("Vehículos y circuitos", "https://www.toysrus.es/Veh%C3%ADculos-y-circuitos/c/Vehiculos_y_circuitos"),
    ("Construcciones & Escenarios", "https://www.toysrus.es/Construcciones-%26-Escenarios/c/005003"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ToysRUsCrawler/1.0)"
}

# ----------------------------------------
# EXPRESIONES REGULARES
# ----------------------------------------

# Precio tipo "29,99 €"
PRICE_REGEX = re.compile(r"(\d+,\d{2})\s*€")

# Marca (si aparece en un span con clase que contenga "brand")
BRAND_REGEX = re.compile(
    r'<span[^>]+class="[^"]*brand[^"]*"[^>]*>\s*(.*?)\s*</span>',
    re.IGNORECASE | re.DOTALL
)

# Edad recomendada (si la hubiera)
AGE_REGEX = re.compile(
    r'<span[^>]+class="[^"]*age[^"]*"[^>]*>\s*(.*?)\s*</span>',
    re.IGNORECASE | re.DOTALL
)


def clean_html_text(text: str) -> str:
    """Quita etiquetas HTML y espacios sobrantes."""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ----------------------------------------
# LOCALIZAR BLOQUES DE PRODUCTO
# ----------------------------------------

def find_product_blocks(soup: BeautifulSoup):
    """
    Intenta encontrar bloques de producto de forma robusta.

    1) Primero busca tags con clase que contenga "product".
    2) Si no hay suerte, como plan B se queda con bloques que tengan:
       - algún precio con "€"
       - al menos un enlace (<a href="...">).
    """
    # 1. Candidatos directos con "product" en la clase
    candidates = []
    for tag_name in ["article", "li", "div"]:
        candidates.extend(
            soup.find_all(tag_name, class_=re.compile("product", re.IGNORECASE))
        )

    if candidates:
        return candidates

    # 2. Fallback genérico: cualquier bloque con precio y enlace
    fallback_blocks = []
    for tag in soup.find_all(["article", "li", "div"]):
        text = tag.get_text(" ", strip=True)
        if "€" in text and PRICE_REGEX.search(text) and tag.find("a", href=True):
            fallback_blocks.append(tag)

    return fallback_blocks


# ----------------------------------------
# EXTRACCIÓN DE CAMPOS DE CADA PRODUCTO
# ----------------------------------------

def extract_products_from_html(html: str, category_label: str):
    """
    Extrae una lista de diccionarios "toy" de una página HTML,
    etiquetando todos con la categoría de esa URL.
    """
    soup = BeautifulSoup(html, "html.parser")
    product_blocks = find_product_blocks(soup)

    products = []

    for block in product_blocks:
        block_html = str(block)

        # ---------- Nombre y URL (con BeautifulSoup) ----------
        a = None
        links = block.find_all("a", href=True)
        if links:
            for link in links:
                text = link.get_text(strip=True)
                if text and len(text) > 3:
                    a = link
                    break

        if not a:
            continue  # sin enlace con texto decente, fuera

        name = a.get_text(" ", strip=True)
        url = a["href"]
        if url.startswith("/"):
            url = "https://www.toysrus.es" + url

        # ---------- Precio (con regex en el HTML bruto del bloque) ----------
        price = None
        price_match = PRICE_REGEX.search(block_html)
        if price_match:
            try:
                price = float(price_match.group(1).replace(",", "."))
            except ValueError:
                price = None

        if price is None:
            # si no hay precio, no lo guardamos
            continue

        # ---------- Marca ----------
        brand_match = BRAND_REGEX.search(block_html)
        brand = clean_html_text(brand_match.group(1)) if brand_match else None

        # ---------- Edad recomendada (si está) ----------
        age_match = AGE_REGEX.search(block_html)
        age_range = clean_html_text(age_match.group(1)) if age_match else None

        # ---------- Imagen ----------
        image_url = None
        img = block.find("img")
        if img and img.get("src"):
            image_url = img["src"]
            # normalizar rutas relativas
            if image_url.startswith("//"):
                image_url = "https:" + image_url
            elif image_url.startswith("/"):
                image_url = "https://www.toysrus.es" + image_url

        # ---------- Construimos el diccionario del juguete ----------
        products.append({
            "name": name,
            "price": price,
            "category": category_label,  # categoría de esa URL (Juegos y Puzzles, etc.)
            "age_range": age_range,
            "brand": brand,
            "url": url,
            "image_url": image_url
        })

    return products


# ----------------------------------------
# FUNCIÓN PRINCIPAL: CRAWLEAR VARIAS CATEGORÍAS
# ----------------------------------------

def crawl_catalog(max_pages_per_category=2):
    """
    Recorre varias categorías de ToysRUs y varias páginas por cada una.

    - max_pages_per_category: cuántas "page=N" probar por cada categoría.
      Para un trabajo de clase 1–3 suele ser suficiente.
    """
    print("Inicializando BBDD...")
    init_db()

    total_inserted = 0

    for category_label, base_url in CATEGORY_PAGES:
        print(f"=== Categoría: {category_label} ===")

        for page in range(1, max_pages_per_category + 1):
            if page == 1:
                url = base_url
                params = {}
            else:
                # muchas categorías soportan ?page=2, ?page=3...
                url = base_url
                params = {"page": page}

            print(f"Crawleando {url} (page={page}) ...")

            try:
                resp = requests.get(url, headers=HEADERS, params=params, timeout=25)
            except Exception as e:
                print(f"  -> Error de red: {e}")
                continue

            if resp.status_code != 200:
                print(f"  -> Error HTTP {resp.status_code}")
                continue

            products = extract_products_from_html(resp.text, category_label)
            print(f"  -> {len(products)} productos encontrados en esta página")

            for toy in products:
                insert_toy(toy)
                total_inserted += 1

            # Pausa para no machacar el servidor
            time.sleep(1.0)

    print(f"Crawling terminado. Productos insertados: {total_inserted}")


if __name__ == "__main__":
    # Puedes subir este número si quieres rascar más páginas por categoría
    crawl_catalog(max_pages_per_category=2)
