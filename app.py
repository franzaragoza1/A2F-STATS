from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlalchemy # Importamos SQLAlchemy
import json
import datetime
import os # Importamos os para leer variables de entorno

# --- Configuración Inicial ---
app = Flask(__name__, template_folder='templates')
CORS(app)

# Nos conectamos a la URL de la BBDD de Render
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///stats.db')
engine = sqlalchemy.create_engine(DATABASE_URL)

# ---------- Crear la base de datos si no existe ----------
def init_db():
    print("Inicializando base de datos...")
    # La sintaxis de CREATE TABLE es estándar y funciona en PostgreSQL
    # 'SERIAL PRIMARY KEY' es el 'AUTOINCREMENT' de PostgreSQL
    create_table_query = """
    CREATE TABLE IF NOT EXISTS partidos (
        id SERIAL PRIMARY KEY,
        fecha TEXT,
        rival TEXT,
        marcador_local INTEGER,
        marcador_rival INTEGER,
        boxscore_json TEXT
    )
    """
    try:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text(create_table_query)) # pyright: ignore[reportUnknownMemberType]
        print("Tabla 'partidos' verificada/creada.")
    except Exception as e:
        print(f"Error al inicializar la BBDD: {e}")

# --- Rutas de la Interfaz de Usuario (Frontend) ---

@app.route("/")
def index():
    """ Sirve la página principal de estadísticas (temporada.html). """
    return render_template("temporada.html")

@app.route("/boxscore")
def boxscore_page():
    """ Sirve la página para registrar un nuevo partido (boxscore.html). """
    return render_template("boxscore.html")

@app.route("/partido/<int:partido_id>")
def ver_partido(partido_id):
    """ Muestra la página de detalle de un partido (detalle_partido.html). """
    query = sqlalchemy.text("SELECT * FROM partidos WHERE id = :id")
    partido_data = {}
    with engine.connect() as conn:
        result = conn.execute(query, {"id": partido_id})
        row = result.fetchone()
        if not row:
            return "Partido no encontrado", 404
        partido_data = dict(row._mapping)

    # Cargamos el JSON del boxscore
    raw_boxscore = json.loads(partido_data["boxscore_json"])
    processed_boxscore = []
    
    if isinstance(raw_boxscore, list):
        for j in raw_boxscore:
            s = j.get('stats', {})
            FGM=s.get('FGM',0); FGA=s.get('FGA',0); TPM=s.get('3PM',0); TPA=s.get('3PA',0); FTM=s.get('FTM',0); FTA=s.get('FTA',0)
            
            pts = (FTM) + (FGM * 2) + (TPM * 3)
            tc = FGM + TPM
            tci = FGA + TPA
            pct = f"{round((tc / tci) * 100)}%" if tci > 0 else "0%"
            tpp = f"{round((TPM / TPA) * 100)}%" if TPA > 0 else "0%"
            ftp = f"{round((FTM / FTA) * 100)}%" if FTA > 0 else "0%"
            
            processed_boxscore.append({
                "number": j.get('number', ''),
                "name": j.get('name', ''),
                "pts": pts,
                "tc": f"{tc}/{tci}", "pct": pct,
                "3p": f"{TPM}/{TPA}", "3ppct": tpp,
                "tl": f"{FTM}/{FTA}", "tlpct": ftp,
                "reb": s.get('REB', 0),
                "ast": s.get('AST', 0),
                "stl": s.get('STL', 0),
                "blk": s.get('BLK', 0),
                "tov": s.get('TOV', 0),
                "pf": s.get('PF', 0)
            })
    
    processed_boxscore.sort(key=lambda x: x.get('number', 0))

    return render_template("detalle_partido.html", 
                           partido=partido_data, 
                           boxscore=processed_boxscore)

# --- Rutas de la API (Backend) ---

@app.route("/guardar_boxscore", methods=["POST"])
def guardar_boxscore():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON vacío"}), 400

        rival = data.get("rival", "Desconocido")
        marcador_local = data.get("marcador_local", 0)
        marcador_rival = data.get("marcador_rival", 0)
        boxscore_json = json.dumps(data.get("boxscore", {}))
        fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        query = sqlalchemy.text(
            "INSERT INTO partidos (fecha, rival, marcador_local, marcador_rival, boxscore_json) VALUES (:fecha, :rival, :marcador_local, :marcador_rival, :boxscore_json)"
        )
        
        with engine.connect() as conn:
            conn.execute(query, {
                "fecha": fecha, 
                "rival": rival, 
                "marcador_local": marcador_local, 
                "marcador_rival": marcador_rival, 
                "boxscore_json": boxscore_json
            })
            conn.commit() # pyright: ignore[reportUnknownMemberType]

        return jsonify({"mensaje": "Boxscore guardado correctamente", "fecha": fecha}), 200

    except Exception as e:
        print(f"Error al guardar: {e}") # Mejoramos el log de error
        return jsonify({"error": str(e)}), 500

@app.route("/partidos", methods=["GET"])
def listar_partidos():
    partidos = []
    try:
        query = sqlalchemy.text("SELECT id, fecha, rival, marcador_local, marcador_rival FROM partidos ORDER BY id DESC")
        with engine.connect() as conn:
            result = conn.execute(query)
            partidos = [dict(row._mapping) for row in result]
    except Exception as e:
        print(f"Error al listar partidos: {e}")
        return jsonify({"error": str(e)}), 500
        
    return jsonify(partidos)

@app.route("/partidos/<int:partido_id>", methods=["GET"])
def detalle_partido(partido_id):
    try:
        query = sqlalchemy.text("SELECT id, fecha, rival, marcador_local, marcador_rival, boxscore_json FROM partidos WHERE id = :id")
        
        with engine.connect() as conn:
            result = conn.execute(query, {"id": partido_id})
            row = result.fetchone()

        if not row:
            return jsonify({"error": "Partido no encontrado"}), 404

        partido_dict = dict(row._mapping)
        partido_dict["boxscore"] = json.loads(partido_dict["boxscore_json"])
        del partido_dict["boxscore_json"]

        return jsonify(partido_dict)
    except Exception as e:
        print(f"Error al obtener detalle: {e}")
        return jsonify({"error": str(e)}), 500

# ---------- Inicio ----------

# ¡¡¡ESTE ES EL CAMBIO CLAVE!!!
# Llamamos a init_db() aquí, en el scope global.
# Se ejecutará UNA VEZ cuando Gunicorn inicie la app.
init_db()

if __name__ == "__main__":
    # init_db() ya no se llama aquí, sino arriba.
    port = int(os.environ.get("PORT", 5000))
    print(f"Servidor Flask iniciado en http://127.0.0.1:{port}")
    # Ejecutamos en 0.0.0.0 para que sea accesible (aunque para prod. se usa Gunicorn)
    app.run(debug=True, host='0.0.0.0', port=port)
