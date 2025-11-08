from io import BytesIO
from flask import send_file
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from flask import jsonify
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime
from flask import send_file
from datetime import datetime
import pytz
import mysql.connector
import qrcode
import io
import qrcode
import random
import requests
import string
import os

app = Flask(__name__)
app.secret_key = "064238"  # Necesaria para manejar sesiones

# Conexión a MySQL

conexion = mysql.connector.connect(
    host=os.getenv("MYSQL_ADDON_HOST", "brodvmtpeyupqyrna1i4-mysql.services.clever-cloud.com"),
    user=os.getenv("MYSQL_ADDON_USER", "uarx8erpufuunofj"),
    password=os.getenv("MYSQL_ADDON_PASSWORD", "5XELE8YVOLPuFjhiI7Xi"),
    database=os.getenv("MYSQL_ADDON_DB", "brodvmtpeyupqyrna1i4"),
    port=int(os.getenv("MYSQL_ADDON_PORT", 3306))
)

tz_mexico = pytz.timezone('America/Mexico_City')
fecha_hora = datetime.now(tz_mexico)

# Ruta principal (inicio)
@app.route('/')
def home():
    if 'usuario' in session:
        return f"Bienvenido, {session['usuario']} ({session['rol']})"
    else:
        return redirect(url_for('login'))
# -------------------------
# Registro de nuevos usuarios
# -------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    mensaje = ""
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        contrasena = request.form['contrasena']
        rol = request.form['rol']

        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE correo = %s", (correo,))
        existe = cursor.fetchone()

        if existe:
            mensaje = "El correo ya está registrado."
        else:
            cursor.execute(
                "INSERT INTO usuarios (nombre, correo, contrasena, rol) VALUES (%s, %s, %s, %s)",
                (nombre, correo, contrasena, rol)
            )
            conexion.commit()
            mensaje = "Usuario registrado correctamente."
        cursor.close()
    return render_template('register.html', mensaje=mensaje)

# -------------------------
# Inicio de sesión
# -------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        contrasena = request.form['contrasena']
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE correo = %s AND contrasena = %s", (correo, contrasena))
        usuario = cursor.fetchone()
        cursor.close()

        if usuario:
            session['usuario'] = usuario['nombre']
            session['rol'] = usuario['rol']
            session['id_usuario'] = usuario['id_usuario']

            # Redirigir según el rol
            if usuario['rol'] == 'Administrador':
                return redirect('/panel_admin')
            elif usuario['rol'] == 'Profesor':
                return redirect('/panel_profesor')
            else:
                return redirect('/panel_alumno')
        else:
            return "Credenciales incorrectas"
    return render_template('login.html')

# -------------------------
# paneles
# -------------------------

@app.route('/panel_admin')
def panel_admin():
    if 'rol' not in session or session['rol'] != 'Administrador':
        return "Acceso denegado"
    return render_template('panel_admin.html', usuario=session['usuario'])

@app.route('/panel_profesor')
def panel_profesor():
    if 'rol' not in session or session['rol'] != 'Profesor':
        return "Acceso denegado"
    return render_template('panel_profesor.html', usuario=session['usuario'])

@app.route('/panel_alumno')
def panel_alumno():
    if 'rol' not in session or session['rol'] != 'Alumno':
        return "Acceso denegado"
    return render_template('panel_alumno.html', usuario=session['usuario'])

# -------------------------
# Cerrar sesión
# -------------------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# -------------------------
# GESTIÓN DE MATERIAS (solo admin)
# -------------------------
@app.route('/materias', methods=['GET', 'POST'])
def materias():
    if 'rol' not in session or session['rol'] != 'Administrador':
        return redirect('/')

    cursor = conexion.cursor()

    if request.method == 'POST':
        nombre = request.form['nombre']  # ← aquí está el cambio
        cursor.execute("INSERT INTO materias (nombre_materia) VALUES (%s)", (nombre,))
        conexion.commit()

    cursor.execute("SELECT id_materia, nombre_materia FROM materias")
    materias = cursor.fetchall()
    cursor.close()

    return render_template('materias.html', materias=materias)


# -------------------------
# GESTIÓN DE GRUPOS (solo admin)
# -------------------------
@app.route('/grupos', methods=['GET', 'POST'])
def grupos():
    if 'rol' not in session or session['rol'] != 'Administrador':
        return redirect('/')

    cursor = conexion.cursor()

    # Crear un nuevo grupo
    if request.method == 'POST' and 'crear_grupo' in request.form:
        nombre = request.form['nombre']
        id_materia = request.form['id_materia']
        id_profesor = request.form['id_profesor']
        cursor.execute("INSERT INTO grupos (nombre_grupo, id_materia, id_profesor) VALUES (%s, %s, %s)",
                       (nombre, id_materia, id_profesor))
        conexion.commit()

    # Cargar materias, profesores y alumnos
    cursor.execute("SELECT id_materia, nombre_materia FROM materias")
    materias = cursor.fetchall()

    cursor.execute("SELECT id_usuario, nombre FROM usuarios WHERE rol = 'Profesor'")
    profesores = cursor.fetchall()

    cursor.execute("SELECT id_usuario, nombre FROM usuarios WHERE rol = 'Alumno'")
    alumnos = cursor.fetchall()

    # Obtener todos los grupos existentes con su materia y profesor
    cursor.execute("""
        SELECT g.id_grupo, g.nombre_grupo, m.nombre_materia, u.nombre AS profesor
        FROM grupos g
        LEFT JOIN materias m ON g.id_materia = m.id_materia
        LEFT JOIN usuarios u ON g.id_profesor = u.id_usuario
    """)
    grupos = cursor.fetchall()

    cursor.close()
    return render_template('grupos.html', grupos=grupos, profesores=profesores, materias=materias, alumnos=alumnos)

@app.route('/eliminar_grupo/<int:id_grupo>')
def eliminar_grupo(id_grupo):
    if 'rol' not in session or session['rol'] != 'Administrador':
        return redirect('/')

    cursor = conexion.cursor()

    # 1. Obtener sesiones del grupo
    cursor.execute("SELECT id_sesion FROM sesiones WHERE id_grupo = %s", (id_grupo,))
    sesiones = cursor.fetchall()

    # 2. Eliminar asistencias de cada sesión
    for (id_sesion,) in sesiones:
        cursor.execute("DELETE FROM asistencias WHERE id_sesion = %s", (id_sesion,))

    # 3. Eliminar sesiones del grupo
    cursor.execute("DELETE FROM sesiones WHERE id_grupo = %s", (id_grupo,))

    # 4. Eliminar relaciones alumno-grupo
    cursor.execute("DELETE FROM alumnos_grupos WHERE id_grupo = %s", (id_grupo,))

    # 5. Eliminar el grupo
    cursor.execute("DELETE FROM grupos WHERE id_grupo = %s", (id_grupo,))

    conexion.commit()
    cursor.close()
    return redirect('/grupos')

@app.route('/agregar_alumno_grupo', methods=['POST'])
def agregar_alumno_grupo():
    if 'rol' not in session or session['rol'] != 'Administrador':
        return redirect('/')

    id_alumno = request.form['id_alumno']
    id_grupo = request.form['id_grupo']

    cursor = conexion.cursor()
    cursor.execute("INSERT INTO alumnos_grupos (id_alumno, id_grupo) VALUES (%s, %s)", (id_alumno, id_grupo))
    conexion.commit()
    cursor.close()
    return redirect('/grupos')


@app.route('/agregar_grupo', methods=['POST'])
def agregar_grupo():
    if 'rol' not in session or session['rol'] != 'Administrador':
        return "Acceso denegado"

    nombre = request.form['nombre_grupo']
    materia = request.form['materia']
    id_profesor = request.form['id_profesor']

    cursor = conexion.cursor()
    cursor.execute("INSERT INTO grupos (nombre_grupo, id_materia, id_profesor) VALUES (%s, %s, %s)",
    (nombre, id_materia, id_profesor))
    conexion.commit()
    cursor.close()

    return redirect('/grupos')

# -------------------------
# lista de alumnos
# -------------------------

@app.route('/grupo/<int:id_grupo>/alumnos', methods=['GET', 'POST'])
def gestionar_alumnos_grupo(id_grupo):
    if 'rol' not in session or session['rol'] != 'Administrador':
        return redirect('/')

    cursor = conexion.cursor()

    # Obtener información del grupo
    cursor.execute("""
        SELECT g.nombre_grupo, m.nombre_materia, u.nombre AS profesor
        FROM grupos g
        LEFT JOIN materias m ON g.id_materia = m.id_materia
        LEFT JOIN usuarios u ON g.id_profesor = u.id_usuario
        WHERE g.id_grupo = %s
    """, (id_grupo,))
    grupo = cursor.fetchone()

    # Agregar alumno al grupo
    if request.method == 'POST' and 'id_alumno' in request.form:
        id_alumno = request.form['id_alumno']
        cursor.execute("""
            INSERT IGNORE INTO alumnos_grupos (id_alumno, id_grupo)
            VALUES (%s, %s)
        """, (id_alumno, id_grupo))
        conexion.commit()

    # Eliminar alumno del grupo
    if request.method == 'POST' and 'eliminar_alumno' in request.form:
        id_alumno_eliminar = request.form['eliminar_alumno']
        cursor.execute("""
            DELETE FROM alumnos_grupos WHERE id_alumno = %s AND id_grupo = %s
        """, (id_alumno_eliminar, id_grupo))
        conexion.commit()

    # Obtener alumnos actuales del grupo
    cursor.execute("""
        SELECT u.id_usuario, u.nombre
        FROM usuarios u
        JOIN alumnos_grupos ag ON u.id_usuario = ag.id_alumno
        WHERE ag.id_grupo = %s
    """, (id_grupo,))
    alumnos_grupo = cursor.fetchall()

    # Obtener lista de alumnos que NO están en el grupo
    cursor.execute("""
        SELECT id_usuario, nombre FROM usuarios
        WHERE rol = 'Alumno' AND id_usuario NOT IN (
            SELECT id_alumno FROM alumnos_grupos WHERE id_grupo = %s
        )
    """, (id_grupo,))
    alumnos_disponibles = cursor.fetchall()

    cursor.close()

    return render_template(
        'alumnos_grupo.html',
        grupo=grupo,
        id_grupo=id_grupo,
        alumnos_grupo=alumnos_grupo,
        alumnos_disponibles=alumnos_disponibles
    )

# -------------------------
# Asignar Grupos
# -------------------------

@app.route('/asignar_alumnos', methods=['GET', 'POST'])
def asignar_alumnos():
    if 'rol' not in session or session['rol'] != 'Administrador':
        return "Acceso denegado"

    id_grupo = request.args.get('id_grupo') or request.form.get('id_grupo')

    cursor = conexion.cursor()

    if request.method == 'POST':
        id_alumno = request.form['id_alumno']
        cursor.execute("INSERT INTO alumnos_grupos (id_alumno, id_grupo) VALUES (%s, %s)", (id_alumno, id_grupo))
        conexion.commit()

    # Obtener alumnos disponibles y actuales
    cursor.execute("SELECT id_usuario, nombre FROM usuarios WHERE rol = 'Alumno'")
    alumnos = cursor.fetchall()

    cursor.execute("""
        SELECT u.nombre
        FROM alumnos_grupos ag
        JOIN usuarios u ON ag.id_alumno = u.id_usuario
        WHERE ag.id_grupo = %s
    """, (id_grupo,))
    asignados = cursor.fetchall()
    cursor.close()

    return render_template('asignar_alumnos.html', id_grupo=id_grupo, alumnos=alumnos, asignados=asignados)



# -------------------------
# GESTIÓN DE SESIONES (solo profesor)
# -------------------------
@app.route('/sesiones', methods=['GET', 'POST'])
def sesiones():
    if 'rol' not in session or session['rol'] != 'Profesor':
        return redirect(url_for('home'))

    cursor = conexion.cursor()

# Obtener los grupos que tiene asignados el profesor con la materia
    cursor.execute("""
    SELECT g.id_grupo, g.nombre_grupo, m.nombre_materia
    FROM grupos g
    LEFT JOIN materias m ON g.id_materia = m.id_materia
    WHERE g.id_profesor = (
        SELECT id_usuario FROM usuarios WHERE nombre = %s
    )
    """, (session['usuario'],))
    grupos = cursor.fetchall()

    # Si el profesor crea una nueva sesión
    if request.method == 'POST':
        id_grupo = request.form['id_grupo']

        # Crear código único aleatorio
        codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Generar QR
# ---------------------------------------------
        import socket

#qr_data = f"http://localhost:5000/registrar_asistencia/{codigo}"

        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        qr_data = f"https://asistencias-qr-sig8.onrender.com/registrar_asistencia/{codigo}"
# ----------------------------------------
        img = qrcode.make(qr_data)

        # Guardar imagen QR
        qr_filename = f"{codigo}.png"
        img.save(os.path.join('static/qrs', qr_filename))

        # Insertar sesión en la base de datos
        cursor.execute("""
            INSERT INTO sesiones (id_grupo, codigo_qr, fecha_hora, duracion_minutos)
            VALUES (%s, %s, %s, %s)
        """, (id_grupo, qr_filename, fecha_hora, 10))
        conexion.commit()

# Mostrar las sesiones existentes del profesor (con materia incluida)
    cursor.execute("""
    SELECT 
        s.id_sesion, 
        s.codigo_qr, 
        g.nombre_grupo, 
        m.nombre_materia, 
        s.fecha_hora
    FROM sesiones s
    JOIN grupos g ON s.id_grupo = g.id_grupo
    LEFT JOIN materias m ON g.id_materia = m.id_materia
    WHERE g.id_profesor = (
        SELECT id_usuario FROM usuarios WHERE nombre = %s
    )
    ORDER BY s.fecha_hora DESC
    """, (session['usuario'],))
    sesiones = cursor.fetchall()

    cursor.close()

    return render_template('sesiones.html', grupos=grupos, sesiones=sesiones)

# -------------------------
# Eliminar seccion 
# -------------------------

@app.route('/eliminar_sesion', methods=['POST'])
def eliminar_sesion():
    if 'rol' not in session or session['rol'] != 'Profesor':
        return redirect(url_for('home'))

    id_sesion = request.form['id_sesion']

    cursor = conexion.cursor()

    # Obtener nombre del archivo QR para borrarlo
    cursor.execute("SELECT codigo_qr FROM sesiones WHERE id_sesion = %s", (id_sesion,))
    qr = cursor.fetchone()
    if qr:
        qr_filename = qr[0]
        qr_path = os.path.join('static/qrs', qr_filename)
        if os.path.exists(qr_path):
            os.remove(qr_path)

    # Eliminar todas las asistencias de esa sesión
    cursor.execute("DELETE FROM asistencias WHERE id_sesion = %s", (id_sesion,))

    # Eliminar la sesión de la base de datos
    cursor.execute("DELETE FROM sesiones WHERE id_sesion = %s", (id_sesion,))
    
    conexion.commit()
    cursor.close()

    return redirect('/sesiones')

# -------------------------
# Registrar Asistencia
# -------------------------
@app.route('/registrar_asistencia/<codigo>', methods=['GET', 'POST'])
def registrar_asistencia(codigo):
    if 'rol' not in session or session['rol'] != 'Alumno':
        return redirect(url_for('home'))

    cursor = conexion.cursor()
    cursor.execute("""
        SELECT id_sesion, fecha_hora, id_grupo 
        FROM sesiones 
        WHERE codigo_qr = %s
    """, (codigo + ".png",))
    sesion = cursor.fetchone()

    if not sesion:
        cursor.close()
        return render_template('asistencia_confirmada.html',
                               estado="error",
                               mensaje="❌ Código QR no válido o inexistente.",
                               ubicacion="No disponible")

    id_sesion, fecha_hora, id_grupo = sesion
    if isinstance(fecha_hora, str):
        fecha_hora = datetime.strptime(fecha_hora, "%Y-%m-%d %H:%M:%S")

    ahora = datetime.now()
    diferencia = (ahora - fecha_hora).total_seconds() / 60

    if request.method == 'GET':
        return render_template('registrar_asistencia.html', codigo=codigo)

    # Recibir ubicación
    latitud = request.form.get('latitud')
    longitud = request.form.get('longitud')

    ubicacion = "No disponible"
    if latitud and longitud:
        try:
            url = f"https://nominatim.openstreetmap.org/reverse?lat={latitud}&lon={longitud}&format=json"
            response = requests.get(url, headers={'User-Agent': 'AsistenciaQRApp'})
            data = response.json()
            ubicacion = data.get('display_name', 'Ubicación desconocida')
        except Exception:
            ubicacion = f"Lat: {latitud}, Lon: {longitud}"

    # Determinar estado
    if diferencia <= 10:
        estado = "Presente"
        mensaje = "✅ Asistencia registrada correctamente."
    elif diferencia <= 20:
        estado = "Tarde"
        mensaje = "⚠️ Asistencia registrada como tarde (se reducirá el porcentaje)."
    else:
        cursor.close()
        return render_template('asistencia_confirmada.html',
                               estado="error",
                               mensaje="⚠️ El código QR ha expirado.",
                               ubicacion=ubicacion)

    # Validar pertenencia
    cursor.execute("""
        SELECT * FROM alumnos_grupos 
        WHERE id_grupo = %s AND id_alumno = (
            SELECT id_usuario FROM usuarios WHERE nombre = %s
        )
    """, (id_grupo, session['usuario']))
    pertenece = cursor.fetchone()

    if not pertenece:
        cursor.close()
        return render_template('asistencia_confirmada.html',
                               estado="error",
                               mensaje="🚫 No perteneces a este grupo.",
                               ubicacion=ubicacion)

    # Verificar duplicado
    cursor.execute("""
        SELECT * FROM asistencias 
        WHERE id_sesion = %s AND id_alumno = (
            SELECT id_usuario FROM usuarios WHERE nombre = %s
        )
    """, (id_sesion, session['usuario']))
    if cursor.fetchone():
        cursor.close()
        return render_template('asistencia_confirmada.html',
                               estado="advertencia",
                               mensaje="⚠️ Ya registraste tu asistencia previamente.",
                               ubicacion=ubicacion)

    # Registrar asistencia
    cursor.execute("""
        INSERT INTO asistencias (id_sesion, id_alumno, fecha_hora_escaneo, ubicacion, estado)
        VALUES (%s, (SELECT id_usuario FROM usuarios WHERE nombre = %s), %s, %s, %s)
    """, (id_sesion, session['usuario'], ahora, ubicacion, estado))
    conexion.commit()
    cursor.close()

    return render_template('asistencia_confirmada.html',
                           estado=estado,
                           mensaje=mensaje,
                           ubicacion=ubicacion)

# -------------------------
# Escanear QR
# -------------------------

@app.route('/escanear_qr')
def escanear_qr():
    if 'rol' not in session or session['rol'] != 'Alumno':
        return redirect(url_for('home'))
    return render_template('escanear_qr.html')


# -------------------------
# REPORTES Y ANALISIS (solo profesor)
# -------------------------

@app.route('/reportes', methods=['GET', 'POST'])
def reportes():
    if 'rol' not in session or session['rol'] not in ['Administrador', 'Profesor']:
        return redirect(url_for('home'))

    cursor = conexion.cursor()

    # Mostrar los grupos según el rol
    if session['rol'] == 'Administrador':
        cursor.execute("""
            SELECT g.id_grupo, g.nombre_grupo, m.nombre_materia
            FROM grupos g
            LEFT JOIN materias m ON g.id_materia = m.id_materia
        """)
    else:
        cursor.execute("""
            SELECT g.id_grupo, g.nombre_grupo, m.nombre_materia
            FROM grupos g
            LEFT JOIN materias m ON g.id_materia = m.id_materia
            WHERE g.id_profesor = (
                SELECT id_usuario FROM usuarios WHERE nombre = %s
            )
        """, (session['usuario'],))
    grupos = cursor.fetchall()

    alumnos_reporte = []
    promedio_asistencia = 0
    id_grupo = None

    if request.method == 'POST':
        id_grupo = request.form['id_grupo']

        # Obtener alumnos del grupo
        cursor.execute("""
            SELECT u.id_usuario, u.nombre
            FROM alumnos_grupos ag
            JOIN usuarios u ON ag.id_alumno = u.id_usuario
            WHERE ag.id_grupo = %s
        """, (id_grupo,))
        alumnos = cursor.fetchall()

        if alumnos:
            # Total de sesiones
            cursor.execute("SELECT COUNT(*) FROM sesiones WHERE id_grupo = %s", (id_grupo,))
            total_sesiones = cursor.fetchone()[0] or 1

            for alumno in alumnos:
                cursor.execute("""
                    SELECT estado
                    FROM asistencias a
                    JOIN sesiones s ON a.id_sesion = s.id_sesion
                    WHERE s.id_grupo = %s AND a.id_alumno = %s
                """, (id_grupo, alumno[0]))
                registros = cursor.fetchall()

                total_asistencia = 0
                for (estado,) in registros:
                    if estado == "Presente":
                        total_asistencia += 1
                    elif estado == "Tarde":
                        total_asistencia += 0.5  # reducción por retraso

                porcentaje = round((total_asistencia / total_sesiones) * 100, 2)
                alumnos_reporte.append((alumno[1], porcentaje))

            # Promedio general del grupo
            promedio_asistencia = round(
                sum(a[1] for a in alumnos_reporte) / len(alumnos_reporte), 2
            )

    cursor.close()

    return render_template(
        'reportes.html',
        grupos=grupos,
        alumnos_reporte=alumnos_reporte,
        promedio_asistencia=promedio_asistencia,
        id_grupo=id_grupo
    )


# -------------------------
# Exportaciones
# -------------------------
@app.route('/exportar_excel', methods=['POST'])
def exportar_excel():
    id_grupo = request.form['id_grupo']
    cursor = conexion.cursor()

    # Obtener datos del grupo y materia
    cursor.execute("""
        SELECT g.nombre_grupo, m.nombre_materia
        FROM grupos g
        JOIN materias m ON g.id_materia = m.id_materia
        WHERE g.id_grupo = %s
    """, (id_grupo,))
    info = cursor.fetchone()
    nombre_grupo, nombre_materia = info

    # Obtener alumnos
    cursor.execute("""
        SELECT u.id_usuario, u.nombre
        FROM alumnos_grupos ag
        JOIN usuarios u ON ag.id_alumno = u.id_usuario
        WHERE ag.id_grupo = %s
    """, (id_grupo,))
    alumnos = cursor.fetchall()

    # Total de sesiones
    cursor.execute("SELECT COUNT(*) FROM sesiones WHERE id_grupo = %s", (id_grupo,))
    total_sesiones = cursor.fetchone()[0] or 1

    # Obtener todas las asistencias del grupo
    cursor.execute("""
        SELECT a.id_alumno, a.estado
        FROM asistencias a
        JOIN sesiones s ON a.id_sesion = s.id_sesion
        WHERE s.id_grupo = %s
    """, (id_grupo,))
    registros = cursor.fetchall()

    # Organizar asistencias por alumno
    asistencias_dict = {}
    for id_alumno, estado in registros:
        asistencias_dict.setdefault(id_alumno, []).append(estado)

    cursor.close()

    # Crear Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte de Asistencia"
    ws.append(["Materia:", nombre_materia])
    ws.append(["Grupo:", nombre_grupo])
    ws.append([])
    ws.append(["Alumno", "% Asistencia"])

    for alumno in alumnos:
        estados = asistencias_dict.get(alumno[0], [])
        total_asistencia = sum(1 if e == "Presente" else 0.5 if e == "Tarde" else 0 for e in estados)
        porcentaje = round((total_asistencia / total_sesiones) * 100, 2)
        ws.append([alumno[1], f"{porcentaje}%"])

    # Guardar Excel en memoria
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f"reporte_{nombre_materia}_{nombre_grupo}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# -------------------------
# Exportar PDF
# -------------------------
@app.route('/exportar_pdf', methods=['POST'])
def exportar_pdf():
    id_grupo = request.form['id_grupo']
    cursor = conexion.cursor()

    # Datos de grupo y materia
    cursor.execute("""
        SELECT g.nombre_grupo, m.nombre_materia
        FROM grupos g
        JOIN materias m ON g.id_materia = m.id_materia
        WHERE g.id_grupo = %s
    """, (id_grupo,))
    info = cursor.fetchone()
    nombre_grupo, nombre_materia = info

    # Obtener alumnos
    cursor.execute("""
        SELECT u.id_usuario, u.nombre
        FROM alumnos_grupos ag
        JOIN usuarios u ON ag.id_alumno = u.id_usuario
        WHERE ag.id_grupo = %s
    """, (id_grupo,))
    alumnos = cursor.fetchall()

    # Total de sesiones
    cursor.execute("SELECT COUNT(*) FROM sesiones WHERE id_grupo = %s", (id_grupo,))
    total_sesiones = cursor.fetchone()[0] or 1

    # Obtener todas las asistencias
    cursor.execute("""
        SELECT a.id_alumno, a.estado
        FROM asistencias a
        JOIN sesiones s ON a.id_sesion = s.id_sesion
        WHERE s.id_grupo = %s
    """, (id_grupo,))
    registros = cursor.fetchall()
    cursor.close()

    # Organizar asistencias por alumno
    asistencias_dict = {}
    for id_alumno, estado in registros:
        asistencias_dict.setdefault(id_alumno, []).append(estado)

    # Crear PDF
    output = BytesIO()
    c = canvas.Canvas(output, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(160, 770, "Reporte de Asistencia")
    c.setFont("Helvetica", 12)
    c.drawString(80, 745, f"Materia: {nombre_materia}")
    c.drawString(80, 730, f"Grupo: {nombre_grupo}")
    c.line(80, 725, 530, 725)

    y = 700
    c.setFont("Helvetica", 11)
    for alumno in alumnos:
        estados = asistencias_dict.get(alumno[0], [])
        total_asistencia = sum(1 if e == "Presente" else 0.5 if e == "Tarde" else 0 for e in estados)
        porcentaje = round((total_asistencia / total_sesiones) * 100, 2)
        c.drawString(80, y, f"{alumno[1]} — {porcentaje}% asistencia")
        y -= 20
        if y < 60:
            c.showPage()
            c.setFont("Helvetica", 11)
            y = 750

    c.save()
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f"reporte_{nombre_materia}_{nombre_grupo}.pdf",
        mimetype="application/pdf"
    )
# -------------------------
# Asistencias (Alumnos)
# -------------------------
@app.route('/mis_asistencias')
def mis_asistencias():
    if 'rol' not in session or session['rol'] != 'Alumno':
        return "Acceso denegado"

    id_alumno = session['id_usuario']
    cursor = conexion.cursor()
    cursor.execute("""
        SELECT s.id_sesion, s.fecha_hora, g.nombre_grupo, a.estado
        FROM asistencias a
        JOIN sesiones s ON a.id_sesion = s.id_sesion
        JOIN grupos g ON s.id_grupo = g.id_grupo
        WHERE a.id_alumno = %s
        ORDER BY s.fecha_hora DESC
    """, (id_alumno,))
    asistencias = cursor.fetchall()
    cursor.close()
    return render_template('mis_asistencias.html', asistencias=asistencias)
# -------------------------
# Gestionar Usuarios
# -------------------------
@app.route('/usuarios', methods=['GET', 'POST'])
def usuarios():
    if 'rol' not in session or session['rol'] != 'Administrador':
        return redirect('/')

    cursor = conexion.cursor()

    # Si el método es POST, agregar nuevo usuario
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        contrasena = request.form['contrasena']
        rol = request.form['rol']

        cursor.execute("""
            INSERT INTO usuarios (nombre, correo, contrasena, rol)
            VALUES (%s, %s, %s, %s)
        """, (nombre, correo, contrasena, rol))
        conexion.commit()

    # Cargar lista de usuarios
    cursor.execute("SELECT id_usuario, nombre, correo, rol FROM usuarios")
    usuarios = cursor.fetchall()
    cursor.close()

    return render_template('usuarios.html', usuarios=usuarios)

# -------------------------
# Gestionar usuarios
# -------------------------

@app.route('/agregar_usuario', methods=['POST'])
def agregar_usuario():
    if 'rol' not in session or session['rol'] != 'Administrador':
        return "Acceso denegado"

    nombre = request.form['nombre']
    correo = request.form['correo']
    contrasena = request.form['contrasena']
    rol = request.form['rol']

    cursor = conexion.cursor()
    cursor.execute("INSERT INTO usuarios (nombre, correo, contrasena, rol) VALUES (%s, %s, %s, %s)",
                   (nombre, correo, contrasena, rol))
    conexion.commit()
    cursor.close()

    return redirect('/usuarios')

@app.route('/eliminar_usuario', methods=['POST'])
def eliminar_usuario():
    if 'rol' not in session or session['rol'] != 'Administrador':
        return "Acceso denegado"

    id_usuario = request.form['id_usuario']
    cursor = conexion.cursor()

    # 1. Eliminar asistencias si el usuario es alumno
    cursor.execute("DELETE FROM asistencias WHERE id_alumno = %s", (id_usuario,))

    # 2. Eliminar relaciones alumno-grupo si es alumno
    cursor.execute("DELETE FROM alumnos_grupos WHERE id_alumno = %s", (id_usuario,))

    # 3. Eliminar grupos si el usuario es profesor
    cursor.execute("SELECT id_grupo FROM grupos WHERE id_profesor = %s", (id_usuario,))
    grupos = cursor.fetchall()
    for (id_grupo,) in grupos:
        # Eliminar asistencias de sesiones del grupo
        cursor.execute("SELECT id_sesion FROM sesiones WHERE id_grupo = %s", (id_grupo,))
        sesiones = cursor.fetchall()
        for (id_sesion,) in sesiones:
            cursor.execute("DELETE FROM asistencias WHERE id_sesion = %s", (id_sesion,))
        # Eliminar sesiones
        cursor.execute("DELETE FROM sesiones WHERE id_grupo = %s", (id_grupo,))
        # Eliminar relaciones alumno-grupo
        cursor.execute("DELETE FROM alumnos_grupos WHERE id_grupo = %s", (id_grupo,))
        # Eliminar grupo
        cursor.execute("DELETE FROM grupos WHERE id_grupo = %s", (id_grupo,))

    # 4. Eliminar el usuario
    cursor.execute("DELETE FROM usuarios WHERE id_usuario = %s", (id_usuario,))

    conexion.commit()
    cursor.close()
    return redirect('/usuarios')

# -------------------------
# Ver asistencia (solo profesor)
# -------------------------
@app.route('/ver_asistencias', methods=['GET', 'POST'])
def ver_asistencias():
    if 'rol' not in session or session['rol'] != 'Profesor':
        return redirect(url_for('home'))

    cursor = conexion.cursor()

    # Obtener los grupos del profesor con el nombre de la materia
    cursor.execute("""
        SELECT g.id_grupo, g.nombre_grupo, m.nombre_materia
        FROM grupos g
        JOIN materias m ON g.id_materia = m.id_materia
        WHERE g.id_profesor = (
            SELECT id_usuario FROM usuarios WHERE nombre = %s
        )
    """, (session['usuario'],))
    grupos = cursor.fetchall()

    sesiones = []
    asistencias = []

    if request.method == 'POST':
        id_grupo = request.form.get('id_grupo')
        id_sesion = request.form.get('id_sesion')

        # Obtener sesiones del grupo
        cursor.execute("""
            SELECT id_sesion, fecha_hora 
            FROM sesiones 
            WHERE id_grupo = %s
            ORDER BY fecha_hora DESC
        """, (id_grupo,))
        sesiones = cursor.fetchall()

        if id_sesion:
            # Obtener alumnos del grupo
            cursor.execute("""
                SELECT u.id_usuario, u.nombre 
                FROM usuarios u
                JOIN alumnos_grupos ag ON u.id_usuario = ag.id_alumno
                WHERE ag.id_grupo = %s
            """, (id_grupo,))
            alumnos = cursor.fetchall()

            # Obtener asistencias registradas en esa sesión
            cursor.execute("""
                SELECT id_alumno, estado, ubicacion
                FROM asistencias 
                WHERE id_sesion = %s
            """, (id_sesion,))
            registros = cursor.fetchall()
            registros_dict = {r[0]: (r[1], r[2]) for r in registros}

            # Armar lista completa
            for alumno in alumnos:
                id_alumno, nombre = alumno
                if id_alumno in registros_dict:
                    estado, ubicacion = registros_dict[id_alumno]
                else:
                    estado = "Ausente"
                    ubicacion = "No disponible"
                asistencias.append((nombre, estado, ubicacion))

    cursor.close()

    return render_template('ver_asistencias.html',
                           grupos=grupos,
                           sesiones=sesiones,
                           asistencias=asistencias)


import socket

if __name__ == '__main__':
    # Detectar la IP local automáticamente
    app.run()

