import os
import json

from flask import Flask, render_template, request
from db import init_db, get_distinct_values, search_toys, get_all_toys

from openai import OpenAI
from dotenv import load_dotenv

# -----------------------------
# Configuración OpenAI + Flask
# -----------------------------

# Cargar variables de entorno (.env)
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Cliente de OpenAI (si hay API key)
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

app = Flask(__name__)

# Crear tabla de BBDD si no existe
init_db()


# -----------------------------
# RUTA PRINCIPAL: CATÁLOGO
# -----------------------------

@app.route("/", methods=["GET"])
def index():
    """
    Página principal del catálogo con filtros.
    """
    # Valores únicos para los combos
    categories = get_distinct_values("category")
    ages = get_distinct_values("age_range")
    brands = get_distinct_values("brand")

    # Filtros actuales (GET)
    category = request.args.get("category") or None
    age_range = request.args.get("age_range") or None
    brand = request.args.get("brand") or None
    order_by = request.args.get("order_by") or "price_asc"

    min_price_str = request.args.get("min_price")
    max_price_str = request.args.get("max_price")

    try:
        min_price = float(min_price_str) if min_price_str else None
    except ValueError:
        min_price = None

    try:
        max_price = float(max_price_str) if max_price_str else None
    except ValueError:
        max_price = None

    toys = search_toys(
        category=category,
        age_range=age_range,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        order_by=order_by
    )

    return render_template(
        "index.html",
        toys=toys,
        total=len(toys),
        categories=categories,
        ages=ages,
        brands=brands,
        selected_category=category,
        selected_age=age_range,
        selected_brand=brand,
        min_price=min_price_str or "",
        max_price=max_price_str or "",
        order_by=order_by
    )


# -----------------------------
# RUTA IA: RECOMENDADOR GPT-5.1
# -----------------------------

@app.route("/ia", methods=["GET", "POST"])
def ia_recommender():
    """
    Página del recomendador IA:

    - GET: muestra formulario para describir el juguete.
    - POST: manda la descripción y el catálogo a GPT-5.1 y
      devuelve una lista de juguetes recomendados.
    """
    query = ""
    results = []
    error_message = None

    if request.method == "POST":
        query = (request.form.get("query") or "").strip()

        if not OPENAI_API_KEY:
            error_message = "No hay API key configurada. Añade OPENAI_API_KEY en el archivo .env."
        elif not client:
            error_message = "No se ha podido crear el cliente de OpenAI."
        elif query:
            try:
                # 1) Cargar todos los juguetes de la BBDD
                toys = get_all_toys()

                if not toys:
                    error_message = "No hay juguetes en la base de datos. Asegúrate de haber ejecutado el crawler."
                else:
                    # 2) Convertir juguetes a texto para pasarlos al modelo
                    toys_text_lines = []
                    for t in toys:
                        line = (
                            f"ID: {t['id']} | "
                            f"Nombre: {t['name']} | "
                            f"Marca: {t['brand']} | "
                            f"Categoría: {t['category']} | "
                            f"Precio: {t['price']} | "
                            f"URL: {t['url']} | "
                            f"Imagen: {t['image_url']}"
                        )
                        toys_text_lines.append(line)

                    toys_text = "\n".join(toys_text_lines)

                    # 3) Instrucciones y prompt
                    system_instructions = (
                        "Eres un recomendador experto de juguetes de una tienda online. "
                        "Tu trabajo es leer la descripción del usuario y elegir los juguetes "
                        "más adecuados de una lista que te damos. Responde siempre en JSON válido."
                    )

                    user_prompt = f"""
Descripción del usuario:
\"\"\"{query}\"\"\"

Aquí tienes el catálogo de juguetes disponibles (uno por línea):
\"\"\"{toys_text}\"\"\"

Elige los 10 juguetes más adecuados para el usuario.
Devuélvelos EXACTAMENTE en formato JSON, sin texto adicional fuera del JSON,
con la siguiente estructura:

[
  {{
    "id": <id_numérico_del_juguete>,
    "name": "nombre",
    "brand": "marca o null",
    "category": "categoría",
    "price": 0.0,
    "url": "url",
    "image_url": "url_imagen_o null"
  }},
  ...
]
"""

                    # 4) Llamada a la API de OpenAI (Responses API)
                    response = client.responses.create(
                        model="gpt-5.1",
                        input=[
                            {"role": "system", "content": system_instructions},
                            {"role": "user", "content": user_prompt},
                        ],
                        max_output_tokens=1500,
                    )

                    # 5) Texto completo generado por el modelo
                    # (forma sencilla y oficial de obtener el texto)
                    raw_text = response.output_text.strip()

                    # 6) Intentar extraer solo el JSON (entre [ y ])
                    json_text = raw_text
                    if "[" in raw_text and "]" in raw_text:
                        json_text = raw_text[raw_text.find("["): raw_text.rfind("]") + 1]

                    try:
                        parsed = json.loads(json_text)
                        if isinstance(parsed, list):
                            results = parsed
                        else:
                            error_message = "La IA no devolvió una lista JSON válida."
                    except Exception as e:
                        print("Error parseando JSON devuelto por OpenAI:", e)
                        error_message = f"No se ha podido interpretar la respuesta de la IA: {e}"

            except Exception as e:
                # Aquí verás el error real en la web y en la consola
                print("Error llamando a OpenAI:", repr(e))
                error_message = f"Error llamando a la IA: {e}"

    return render_template(
        "ia.html",
        query=query,
        results=results,
        total=len(results),
        error_message=error_message
    )


# -----------------------------
# MAIN
# -----------------------------

if __name__ == "__main__":
    app.run(debug=True)
