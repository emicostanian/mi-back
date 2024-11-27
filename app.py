from flask_cors import CORS
from flask import Flask, request, jsonify
import mysql.connector
import jwt
import datetime

app = Flask(__name__)
CORS(app)
SECRET_KEY = '648488465184481'

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
    query = "SELECT l.correo, l.contraseña, a.ci  FROM login l JOIN alumnos a ON l.correo = a.correo WHERE l.correo = %s AND l.contraseña = %s"
    cursor.execute(query, (correo, contraseña))
    usuario = cursor.fetchone()
    print(cursor)
    if usuario:
        # Determinar el rol según el dominio del correo
        if '@correo.ucu.edu.uy' in correo:
            rol = 'student'
        elif '@ucu.edu.uy' in correo:
            rol = 'instructor'
        elif '@gmail.com' in correo:
            rol = 'administrador'
        else:
            rol = 'Desconocido'  # O cualquier valor por defecto si no corresponde a ninguno

        # Generar el token JWT
        payload = {
            "correo": usuario['correo'],
            "rol": rol,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=5),  # El token expirará en 1 hora
            "ci": usuario["ci"]
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        cedula = usuario["ci"]
        return jsonify({
            "message": "Login exitoso",
            "token": token,  # Devolver el token generado
            "role": rol, 
            "ci": cedula
        }), 200
    else:
        return jsonify({"error": "Correo o contraseña inválidos"}), 401
    
def verificar_token():
    # Obtener el token del encabezado Authorization
    token = request.headers.get('Authorization')

    if not token:
        return jsonify({"error": "Token no proporcionado"}), 403

    try:
        # Eliminar el prefijo 'Bearer ' si existe
        token = token.replace("Bearer ", "")

        # Verificar el token usando la clave secreta
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return decoded  # Retornar el payload decodificado
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "El token ha expirado"}), 403
    except jwt.InvalidTokenError:
        return jsonify({"error": "Token inválido"}), 403
    
@app.route('/clases/<int:id_actividad>', methods=['GET'])
def obtener_clases_por_actividad(id_actividad):
    cursor = db.cursor(dictionary=True)
    try:
        query = """
            SELECT c.id, c.fecha_clase, c.tipo_clase, c.dictada, 
                   i.nombre AS instructor_nombre, i.apellido AS instructor_apellido 
            FROM clase c
            JOIN instructores i ON c.ci_instructor = i.ci
            WHERE c.id_actividad = %s
        """
        cursor.execute(query, (id_actividad,))
        clases = cursor.fetchall()
        return jsonify(clases), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/inscripciones', methods=['GET'])
def obtener_inscripciones():
    cursor = db.cursor(dictionary=True)
    try:
        query = """
            SELECT 
                ac.id_clase,
                a.ci AS alumno_ci,
                a.nombre AS alumno_nombre,
                a.apellido AS alumno_apellido,
                c.fecha_clase,
                c.tipo_clase,
                c.dictada,
                ac.costo_total
            FROM 
                alumno_clase ac
            JOIN 
                alumnos a ON ac.ci_alumno = a.ci
            JOIN 
                clase c ON ac.id_clase = c.id;
        """
        cursor.execute(query)
        inscripciones = cursor.fetchall()
        return jsonify(inscripciones), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500




# -------------------- ABM de Instructores --------------------
@app.route('/instructores', methods=['GET'])
def instructores():
     # Verificar el token antes de ejecutar la lógica
    decoded_token = verificar_token()
    if isinstance(decoded_token, tuple):  # Si la respuesta es un error
        return decoded_token
    cursor = db.cursor(dictionary=True)
    if request.method == 'GET':
        cursor.execute("SELECT * FROM instructores")
        return jsonify(cursor.fetchall())
    
@app.route('/clases_estado/<int:ci_alumno>', methods=['GET'])
def obtener_clases_estado_para_alumno(ci_alumno):
    cursor = db.cursor(dictionary=True)
    try:
        query = """
            SELECT 
                c.id AS clase_id,
                c.fecha_clase,
                c.tipo_clase,
                c.dictada,
                i.nombre AS instructor_nombre,
                i.apellido AS instructor_apellido,
                t.hora_inicio AS turno_inicio,
                t.hora_fin AS turno_fin,
                CASE
                    WHEN ac.ci_alumno IS NOT NULL THEN 'Inscrito'
                    ELSE 'No Inscrito'
                END AS estado_inscripcion
            FROM clase c
            JOIN turnos t ON c.id_turno = t.id
            JOIN instructores i ON c.ci_instructor = i.ci
            LEFT JOIN alumno_clase ac ON c.id = ac.id_clase AND ac.ci_alumno = %s
        """
        cursor.execute(query, (ci_alumno,))
        clases = cursor.fetchall()
        
        # Serializar campos de tiempo
        for clase in clases:
            clase['turno_inicio'] = serialize_timedelta(clase['turno_inicio'])
            clase['turno_fin'] = serialize_timedelta(clase['turno_fin'])
        
        return jsonify(clases), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/verificar_inscripcion', methods=['POST'])
def verificar_inscripcion():
    data = request.json
    ci_alumno = data.get('ci_alumno')
    id_clase = data.get('id_clase')
    cursor = db.cursor(dictionary=True)
    try:
        query = """
            SELECT * FROM alumno_clase
            WHERE ci_alumno = %s AND id_clase = %s
        """
        cursor.execute(query, (ci_alumno, id_clase))
        inscripcion = cursor.fetchone()
        if inscripcion:
            return jsonify({"inscripto": True}), 200
        else:
            return jsonify({"inscripto": False}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/clases/disponibles', methods=['GET'])
def obtener_clases_disponibles():
    cursor = db.cursor(dictionary=True)
    try:
        query = """
            SELECT c.id, c.fecha_clase, c.tipo_clase, c.dictada, 
                   i.nombre AS instructor_nombre, i.apellido AS instructor_apellido,
                   a.descripcion AS actividad
            FROM clase c
            JOIN instructores i ON c.ci_instructor = i.ci
            JOIN actividades a ON c.id_actividad = a.id
            WHERE c.dictada = 0  -- Clases no dictadas
        """
        cursor.execute(query)
        clases = cursor.fetchall()
        return jsonify(clases), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
   



@app.route('/clases/<int:id>/inscribirse', methods=['POST'])
def inscribirse_a_clase(id):
    
    cursor = db.cursor(dictionary=True)
    data = request.json
    print(request)
    print(data)
    print(id)
    ci_alumno = data.get('ci_alumno')  # Cédula del alumno
    id_clase = id

    if not ci_alumno or not id_clase:
        return jsonify({"error": "Faltan campos obligatorios (ci_alumno, id_clase)"}), 400

    try:
        # Verificar si el alumno ya está inscrito en la clase
        query_verificar = "SELECT * FROM alumno_clase WHERE ci_alumno = %s AND id_clase = %s"
        cursor.execute(query_verificar, (ci_alumno, id_clase))
        if cursor.fetchone():
            return jsonify({"error": "Ya estás inscrito en esta clase"}), 400

        # Inscribir al alumno
        query_inscribir = "INSERT INTO alumno_clase (ci_alumno, id_clase) VALUES (%s, %s)"
        cursor.execute(query_inscribir, (ci_alumno, id_clase))
        db.commit()
        return jsonify({"message": "Inscripción exitosa"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/equipamiento/disponible', methods=['GET'])
def obtener_equipamiento_disponible():
    """Obtener lista de equipamiento disponible para alquiler."""
    cursor = db.cursor(dictionary=True)
    try:
        query = "SELECT * FROM equipamiento WHERE disponible = 1"
        cursor.execute(query)
        equipamiento = cursor.fetchall()
        return jsonify(equipamiento), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/equipamiento/alquilar', methods=['POST'])
def alquilar_equipamiento():
    """Registrar un alquiler de equipamiento para un alumno."""
    cursor = db.cursor(dictionary=True)
    data = request.json

    ci_alumno = data.get('ci_alumno')
    id_equipamiento = data.get('id_equipamiento')

    if not ci_alumno or not id_equipamiento:
        return jsonify({"error": "Faltan campos obligatorios (ci_alumno, id_equipamiento)"}), 400

    try:
        # Verificar si el equipo está disponible
        query_disponible = "SELECT * FROM equipamiento WHERE id = %s AND disponible = 1"
        cursor.execute(query_disponible, (id_equipamiento,))
        equipamiento = cursor.fetchone()

        if not equipamiento:
            return jsonify({"error": "El equipamiento no está disponible"}), 400

        # Registrar el alquiler
        query_alquilar = """
            INSERT INTO alumno_equipamiento (ci_alumno, id_equipamiento, fecha_alquiler)
            VALUES (%s, %s, NOW())
        """
        cursor.execute(query_alquilar, (ci_alumno, id_equipamiento))
        
        # Marcar el equipo como no disponible
        query_actualizar = "UPDATE equipamiento SET disponible = 0 WHERE id = %s"
        cursor.execute(query_actualizar, (id_equipamiento,))

        db.commit()
        return jsonify({"message": "Equipamiento alquilado con éxito"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/equipamiento/alquilado/<int:ci_alumno>', methods=['GET'])
def obtener_equipamiento_alquilado(ci_alumno):
    """Obtener lista de equipos alquilados por un alumno."""
    cursor = db.cursor(dictionary=True)
    try:
        query = """
            SELECT ae.id_equipamiento, e.nombre, e.descripcion, ae.fecha_alquiler
            FROM alumno_equipamiento ae
            JOIN equipamiento e ON ae.id_equipamiento = e.id
            WHERE ae.ci_alumno = %s
        """
        cursor.execute(query, (ci_alumno,))
        alquilado = cursor.fetchall()
        return jsonify(alquilado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/clases/inscritas/<int:ci_alumno>', methods=['GET'])
def obtener_clases_inscritas(ci_alumno):
    cursor = db.cursor(dictionary=True)
    try:
        query = """
            SELECT c.id, c.fecha_clase, c.tipo_clase, 
                   a.descripcion AS actividad,
                   i.nombre AS instructor_nombre, i.apellido AS instructor_apellido
            FROM alumno_clase ac
            JOIN clase c ON ac.id_clase = c.id
            JOIN actividades a ON c.id_actividad = a.id
            JOIN instructores i ON c.ci_instructor = i.ci
            WHERE ac.ci_alumno = %s
        """
        cursor.execute(query, (ci_alumno,))
        clases = cursor.fetchall()
        return jsonify(clases), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

@app.route('/api/alumno/ci', methods=['GET'])
def obtener_ci_alumno():
    """Devuelve el CI del alumno autenticado o relacionado."""
    # Obtener el token para identificar al usuario (si aplica)
    decoded_token = verificar_token()
    if isinstance(decoded_token, tuple):  # Si la respuesta es un error
        return decoded_token

    # Aquí asumimos que el token incluye el correo o identificación del usuario
    correo = decoded_token.get('correo')  # Ejemplo: recuperar correo del token

    cursor = db.cursor(dictionary=True)
    try:
        # Buscar el CI del alumno usando su correo (u otro identificador)
        query = "SELECT ci FROM alumnos WHERE correo = %s"
        cursor.execute(query, (correo,))
        alumno = cursor.fetchone()

        if not alumno:
            return jsonify({"error": "Alumno no encontrado"}), 404

        return jsonify({"ci": alumno['ci']}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------- ABM de Clases --------------------
@app.route('/actividades', methods=['GET', 'POST', 'PUT', 'DELETE'])
def actividades():
    cursor = db.cursor(dictionary=True)
    if request.method == 'GET':
        cursor.execute("SELECT * FROM actividades")
        return jsonify(cursor.fetchall()), 200
    elif request.method == 'POST':
        data = request.json
        query = "INSERT INTO actividades (title, description, players, categories) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (data['title'], data['description'], data['players'], data['categories']))
        db.commit()
        return jsonify({"message": "Clase creada exitosamente"}), 201
    elif request.method == 'PUT':
        data = request.json
        query = "UPDATE actividades SET title=%s, description=%s, players=%s, categories=%s WHERE id=%s"
        cursor.execute(query, (data['title'], data['description'], data['players'], data['categories'], data['id']))
        db.commit()
        return jsonify({"message": "Clase actualizada exitosamente"}), 200
    elif request.method == 'DELETE':
        class_id = request.args.get('id')
        cursor.execute("DELETE FROM actividades WHERE id=%s", (class_id,))
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
