from flask import Flask, request, jsonify
import mysql.connector

app = Flask(__name__)

# Configuración de la base de datos
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="rootpassword",
    database="EscuelaDeNieveUCU"
)

# Función para convertir timedelta a formato HH:MM:SS
def serialize_timedelta(td):
    if isinstance(td, (str, type(None))):  # Si ya es string o None, devuélvelo
        return td
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}"

# Endpoint raíz
@app.route('/')
def index():
    return "¡Backend funcionando correctamente!"

# -------------------- Login --------------------
@app.route('/login', methods=['POST'])
def login():
    cursor = db.cursor(dictionary=True)
    data = request.json

    # Validar que los campos estén presentes
    correo = data.get('correo')
    contraseña = data.get('contraseña')

    if not correo or not contraseña:
        return jsonify({"error": "Faltan campos obligatorios (correo y contraseña)"}), 400

    # Consulta a la base de datos para verificar las credenciales
    query = "SELECT * FROM login WHERE correo = %s AND contraseña = %s"
    cursor.execute(query, (correo, contraseña))
    usuario = cursor.fetchone()

    if usuario:
        return jsonify({"message": "Login exitoso", "correo": usuario['correo']}), 200
    else:
        return jsonify({"error": "Correo o contraseña inválidos"}), 401

# -------------------- ABM de Instructores --------------------
@app.route('/instructores', methods=['GET', 'POST', 'PUT', 'DELETE'])
def instructores():
    cursor = db.cursor(dictionary=True)
    if request.method == 'GET':
        cursor.execute("SELECT * FROM instructores")
        return jsonify(cursor.fetchall())
    elif request.method == 'POST':
        data = request.json
        cursor.execute("INSERT INTO instructores (ci, nombre, apellido) VALUES (%s, %s, %s)",
                       (data['ci'], data['nombre'], data['apellido']))
        db.commit()
        return jsonify({"message": "Instructor creado exitosamente"}), 201
    elif request.method == 'PUT':
        data = request.json
        cursor.execute("UPDATE instructores SET nombre=%s, apellido=%s WHERE ci=%s",
                       (data['nombre'], data['apellido'], data['ci']))
        db.commit()
        return jsonify({"message": "Instructor actualizado exitosamente"})
    elif request.method == 'DELETE':
        ci = request.args.get('ci')
        cursor.execute("DELETE FROM instructores WHERE ci=%s", (ci,))
        db.commit()
        return jsonify({"message": "Instructor eliminado exitosamente"})

# -------------------- ABM de Turnos --------------------
@app.route('/turnos', methods=['GET', 'POST', 'PUT', 'DELETE'])
def turnos():
    cursor = db.cursor(dictionary=True)
    if request.method == 'GET':
        cursor.execute("SELECT * FROM turnos")
        turnos = cursor.fetchall()
        for turno in turnos:
            turno['hora_inicio'] = serialize_timedelta(turno['hora_inicio'])
            turno['hora_fin'] = serialize_timedelta(turno['hora_fin'])
        return jsonify(turnos)
    elif request.method == 'POST':
        data = request.json
        cursor.execute("INSERT INTO turnos (hora_inicio, hora_fin) VALUES (%s, %s)",
                       (data['hora_inicio'], data['hora_fin']))
        db.commit()
        return jsonify({"message": "Turno creado exitosamente"}), 201
    elif request.method == 'PUT':
        data = request.json
        cursor.execute("UPDATE turnos SET hora_inicio=%s, hora_fin=%s WHERE id=%s",
                       (data['hora_inicio'], data['hora_fin'], data['id']))
        db.commit()
        return jsonify({"message": "Turno actualizado exitosamente"})
    elif request.method == 'DELETE':
        turno_id = request.args.get('id')
        cursor.execute("DELETE FROM turnos WHERE id=%s", (turno_id,))
        db.commit()
        return jsonify({"message": "Turno eliminado exitosamente"})

# -------------------- ABM de Clases --------------------
@app.route('/clases', methods=['GET', 'POST', 'PUT', 'DELETE'])
def clases():
    cursor = db.cursor(dictionary=True)
    if request.method == 'GET':
        cursor.execute("SELECT * FROM clases")
        return jsonify(cursor.fetchall()), 200
    elif request.method == 'POST':
        data = request.json
        query = "INSERT INTO clases (title, description, players, categories) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (data['title'], data['description'], data['players'], data['categories']))
        db.commit()
        return jsonify({"message": "Clase creada exitosamente"}), 201
    elif request.method == 'PUT':
        data = request.json
        query = "UPDATE clases SET title=%s, description=%s, players=%s, categories=%s WHERE id=%s"
        cursor.execute(query, (data['title'], data['description'], data['players'], data['categories'], data['id']))
        db.commit()
        return jsonify({"message": "Clase actualizada exitosamente"}), 200
    elif request.method == 'DELETE':
        class_id = request.args.get('id')
        cursor.execute("DELETE FROM clases WHERE id=%s", (class_id,))
        db.commit()
        return jsonify({"message": "Clase eliminada exitosamente"}), 200

# -------------------- Reportes --------------------
@app.route('/reportes', methods=['GET'])
def reportes():
    cursor = db.cursor(dictionary=True)
    tipo = request.args.get('tipo')

    if tipo == 'ingresos':
        query = """
        SELECT 
            actividades.descripcion,
            SUM(actividades.costo + IFNULL(equipamiento.costo, 0)) AS ingresos
        FROM clase
        JOIN actividades ON clase.id_actividad = actividades.id
        LEFT JOIN reservas_equipamiento ON clase.id = reservas_equipamiento.id_clase
        LEFT JOIN equipamiento ON reservas_equipamiento.id_equipamiento = equipamiento.id
        GROUP BY actividades.id
        ORDER BY ingresos DESC;
        """
        cursor.execute(query)
        return jsonify(cursor.fetchall())

    elif tipo == 'alumnos':
        query = """
        SELECT 
            actividades.descripcion,
            COUNT(alumno_clase.ci_alumno) AS cantidad_alumnos
        FROM clase
        JOIN actividades ON clase.id_actividad = actividades.id
        JOIN alumno_clase ON clase.id = alumno_clase.id_clase
        GROUP BY actividades.id
        ORDER BY cantidad_alumnos DESC;
        """
        cursor.execute(query)
        return jsonify(cursor.fetchall())

    elif tipo == 'turnos':
        query = """
        SELECT 
            CONCAT(turnos.hora_inicio, '-', turnos.hora_fin) AS turno,
            COUNT(*) AS cantidad_clases
        FROM clase
        JOIN turnos ON clase.id_turno = turnos.id
        GROUP BY turnos.id
        ORDER BY cantidad_clases DESC;
        """
        cursor.execute(query)
        turnos = cursor.fetchall()
        for turno in turnos:
            turno['turno'] = serialize_timedelta(turno['turno'])
        return jsonify(turnos)

    return jsonify({"error": "Tipo de reporte no válido. Opciones: ingresos, alumnos, turnos"}), 400

# Iniciar servidor
if __name__ == '__main__':
    app.run(debug=True, port=5000)
