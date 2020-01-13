from flask import Flask, request, send_from_directory
from flask_restful import Resource, Api
from flask_cors import CORS
from escpos.printer import Serial
import sqlite3

conn = sqlite3.connect('mydatabase.db', check_same_thread=False)

app = Flask(__name__)
CORS(app)
api = Api(app)

claves_utiles = [str(x) for x in range(20)]
claves_usadas = [""]
claves_admin = ["1111"]
resultados = {}

boleta = [
    {
        "logo": "image/PAN.jpg",
		"candidato": "PEDRO PEREZ PEREIRA",
		"partido": "PAN",
		"id": 123	
    },
    {
        "logo": "image/PRI.jpeg",
		"candidato": "JUANA LOPEZ LOPEZ",
		"partido": "PRI",
		"id": 456	
    },
    {
        "logo": "image/MORENA.png",
		"candidato": "PANCHO MENDEZ MENDEZ",
		"partido": "MORENA",
		"id": 789	
    },
    {
        "logo": "image/PRD.png",
		"candidato": "MANUEL RAMIREZ RAMIREZ",
		"partido": "PRD",
		"id": 426	
    }
]

@app.route('/image/<path:path>')
def send_image(path):
    return send_from_directory('image', path)

class Login(Resource):
    def post(self):
        req = request.get_json()
        if "clave" in req:
            clave = req["clave"]
            status = check_user(conn, clave)
            return {"status": status}
        
        return {"error": "bad request"}


class Boleta(Resource):
    def get(self):
        db_boleta = get_boleta(conn)
        return db_boleta


class Votar(Resource):
    def post(self):
        req = request.get_json()
        status = 1
        mensaje = ""
        if "clave" in req and "id" in req:
            clave = req["clave"]
            voto = req["id"]
            db_user_clave = check_user(conn, clave)
            if db_user_clave == 0:
                partido = ""
                partido_id = ""
                candidato = ""

                db_boleta = get_boleta(conn)
                for part in db_boleta:
                    if part["id"] == voto:
                        partido = part["partido"]
                        partido_id = part["id"]
                        candidato = part["candidato"]
                        break
                else:
                    err = "no se encontró el partido {}". format(voto)
                    print(err)
                    return {"status": status, "mensaje": err}
                print_voto(candidato, partido)

                # Registrar voto
                registrar_voto(conn, partido_id, clave)
                status = 0
            elif db_user_clave == 2:
                mensaje = "clave ya usada"
            elif db_user_clave == 3:
                mensaje = "clave de admin no puede votar"
            else:
                mensaje = "clave no encontrada"
            if mensaje == "":
                return {"status": status}
            return {"status": status, "mensaje": mensaje}
                
        
        return {"status": status, "mensaje": "bad request"}


class Lista(Resource):
    def post(self):
        req = request.get_json()
        if "clave" in req:
            clave = req["clave"]
            status = check_user(conn, clave)
            if status == 3:
                # Imprimir resultados
                db_resultados = get_resultados(conn)
                print_result(db_resultados)
                return
            else:
                return {"error": "no autorizado"}
        
        return {"error": "bad request"}



api.add_resource(Login, '/login')
api.add_resource(Boleta, '/boleta')
api.add_resource(Votar, '/votar')
api.add_resource(Lista, "/lista")

## PRINTER
def print_voto(candidato, partido):
    p = Serial('COM1')
    p.text("\n============VOTO============\n\n\n\n")
    p.text("PARTIDO: {}\n\n".format(partido))
    p.text("CANDIDATO: {}\n\n".format(candidato))
    p.text("============VOTO============\n\n")
    p.cut()
    p.close()

def print_result(db_result):
    p = Serial('COM1')
    p.text("\n============RESULTADOS============\n\n\n\n")
    for row in db_result:
        p.text("{}\n\n".format(db_result))
    p.text("============RESULTADOS============\n\n")
    p.cut()
    p.close()


## DATABASE

def prepare_database(con):
    cursorObj = con.cursor()
    cursorObj.execute("CREATE TABLE usuarios(id integer PRIMARY KEY, clave text, admin bool, used bool)")
    con.commit()

    cursorObj.execute("CREATE TABLE boleta(id integer PRIMARY KEY, clave text, partido text, candidato text, logo text)")
    con.commit()

    cursorObj.execute("CREATE TABLE resultado(id integer PRIMARY KEY, partido text, total integer)")
    con.commit()

def insert_user(con, user, admin):
    cursorObj = con.cursor()
    entities = (user, user, admin, False)
    cursorObj.execute('''INSERT INTO usuarios(id, clave, admin, used) VALUES(?, ?, ?, ?)''', entities)

    con.commit()

def insert_partido(con, partido):
    cursorObj = con.cursor()
    entities = (partido["id"], partido["id"], partido["partido"], partido["candidato"], partido["logo"])
    cursorObj.execute('''INSERT INTO boleta(id, clave, partido, candidato, logo) VALUES(?, ?, ?, ?, ?)''', entities)
    con.commit()
    entities = (partido["id"], partido["partido"], 0)
    cursorObj.execute('''INSERT INTO resultado(id, partido, total) VALUES(?, ?, ?)''', entities)

    con.commit()

def check_user(con, clave):
    cursorObj = con.cursor()
    cursorObj.execute('SELECT * FROM usuarios WHERE clave=?', (clave,))
 
    rows = cursorObj.fetchall()

    if len(rows) == 0:
        return 1
    if rows[0][2]:
        return 3
    if rows[0][3]:
        return 2
    return 0

def get_boleta(con):
    cursorObj = con.cursor()
    cursorObj.execute('SELECT * FROM boleta')

    rows = cursorObj.fetchall()

    res = []

    for part in rows:
        res.append({
            "id": part[1],
            "partido": part[2],
            "candidato": part[3],
            "logo": part[4]
        })
    return res

def registrar_voto(con, partido_id, clave_user):
    cursorObj = con.cursor()
    cursorObj.execute('UPDATE resultado SET total = total + 1 WHERE id=?', (partido_id,))
    con.commit()

    cursorObj.execute('UPDATE usuarios SET used = true WHERE id=?', (clave_user,))
    con.commit()

def get_resultados(con):
    cursorObj = con.cursor()
    cursorObj.execute('SELECT * FROM resultado')

    rows = cursorObj.fetchall()

    res = []

    for part in rows:
        res.append({
            "id": part[0],
            "partido": part[1],
            "total": part[2]
        })
    return res


if __name__ == '__main__':
    # Crear tablas
    try:
        prepare_database(conn)
    except Exception as e:
        print(e)

    # Crear usuarios
    try:
        for user in claves_utiles:
            insert_user(conn, user, False)
        for user in claves_admin:
            insert_user(conn, user, True)
    except Exception as e:
        print(e)
    
    # Crear boleta
    try:
        for partido in boleta:
            insert_partido(conn, partido)
    except Exception as e:
        print(e)
    
    app.run(debug=True, host='0.0.0.0', port='8000')