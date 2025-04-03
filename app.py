from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
import os
from dotenv import load_dotenv
from functools import wraps
load_dotenv()


app = Flask(__name__)
app.secret_key = "secret123" 

host = os.getenv("DB_HOST", "bla")
print(host)


users = {
    "admin": {"password": "password123", "role": "admin"},
    "user": {"password": "pass123", "role": "user"}
}
arr=['Entry','Update','Display','List','Delete'] #Crud 
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "mypassword"),
        database=os.getenv("DB_NAME", "ecom"),
        collation="utf8mb4_unicode_ci"
    )

@app.route("/dashboard")
def get_tables():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name <> 'Admin';")
    data = cursor.fetchall()
    print(data)  # Debugging: Print the fetched data to the console
    cursor.close()
    conn.close()
    print("connected")
    return render_template("index1.html", tables=data)

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username in users and users[username]["password"] == password:
            session["user"] = username
            session["role"] = users[username]["role"]
            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Invalid Credentials")

    return render_template("login.html")

@app.route("/logout")
def logout():
    # Clear the session
    session.clear()
    # Redirect to the login page
    return redirect(url_for("login"))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "role" not in session or session["role"] != "admin":
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("index1.html", username=session["user"])

def get_FKdata(table):
    Id=table+'Id'
    Name=table
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)  
    cursor.execute(f"select {Name} as Name , {Id} as Id from {table}")
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return data

def get_metadata(table):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)  
    cursor.execute(f"DESCRIBE {table}")
    data = cursor.fetchall()
    print(data)
    cursor.close()
    conn.close() 
    
    meta = []
    FK=''
    for dt in data:
        if dt['Key'] == 'PRI' or 'datetime' in dt['Type']:  
            continue
        input_type = 'text'
        if dt['Field']=='Passwd':
            input_type='password'
        elif 'varchar' in dt['Type']:
            input_type = 'text'
        elif 'char(1)' in dt['Type']:
            input_type = 'radio'
        elif 'int(8)' in dt['Type']:
            input_type='FK'
            FK=get_FKdata(dt['Field'])   
               
        elif 'int' in dt['Type']:
            input_type = 'number'
        meta.append({'id':id,'name': dt['Field'], 'type': input_type ,'FK':FK})
    
    return meta

@app.route("/Entry/<tablename>")
def Entry(tablename):
    table=f'{tablename}'
    metadata = get_metadata(table)
    metadata.append({'tablename':table})
    return render_template('CreateSubmit.html', metadata=metadata)

@app.route("/CreateSubmit/<tablename>", methods=["POST"])
def CreateSubmit(tablename):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(f'DESCRIBE {tablename}')
    data = cursor.fetchall()

    fields = [] 
    values = []  

    for dt in data:
        if dt['Key'] == 'PRI' or 'datetime' in dt['Type']:  
            continue
        fields.append(dt['Field'])
        values.append(request.form.get(dt['Field']))  

    placeholders = ", ".join(["%s"] * len(fields))
    query = f"INSERT INTO {tablename} ({', '.join(fields)}) VALUES ({placeholders})"

    cursor.execute(query, values)
    conn.commit()  

    cursor.close()
    conn.close()
    return redirect(url_for('Entry',tablename=tablename))  

@app.route("/Update/<tablename>/<record_id>")
def Update(tablename, record_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(f"DESCRIBE {tablename}")
    metadata = cursor.fetchall()
    cursor.execute(f"SELECT * FROM {tablename} WHERE {tablename}Id = %s", (record_id,))
    record = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template("update.html", metadata=metadata, record=record, tablename=tablename)

@app.route("/UpdateSubmit/<tablename>/<record_id>", methods=["POST"])
def UpdateSubmit(tablename, record_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"DESCRIBE {tablename}")
    metadata = cursor.fetchall()

    updates = []
    values = []
    for field in metadata:
        if field["Key"] == "PRI" or "datetime" in field["Type"]:
            continue
        value = request.form.get(field["Field"])
        updates.append(f"{field['Field']} = %s")
        values.append(value)

    query = f"UPDATE {tablename} SET {', '.join(updates)} WHERE {tablename}Id = %s"
    values.append(record_id)
    cursor.execute(query, values)
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("dashboard"))

@app.route("/Delete/<tablename>/<record_id>")
def Delete(tablename, record_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = f"DELETE FROM {tablename} WHERE {tablename}Id = %s"
    cursor.execute(query, (record_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("dashboard"))

@app.route("/Display/<tablename>")
def Display(tablename):
    page = request.args.get("page", 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(f"SELECT * FROM {tablename} LIMIT %s OFFSET %s", (per_page, offset))
    records = cursor.fetchall()
    cursor.execute(f"SELECT COUNT(*) AS total FROM {tablename}")
    total = cursor.fetchone()["total"]
    cursor.close()
    conn.close()

    return render_template(
        "display.html",
        records=records,
        tablename=tablename,
        page=page,
        total_pages=(total // per_page) + (1 if total % per_page > 0 else 0)
    )

@app.route("/List/<tablename>")
def List(tablename):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch the first two columns of the table
        cursor.execute(f"DESCRIBE {tablename}")
        columns = cursor.fetchall()
        if len(columns) < 2:
            return render_template("error.html", message=f"Table {tablename} does not have enough columns.")

        first_column = columns[0]["Field"]
        second_column = columns[1]["Field"]

        # Fetch data for the first two columns
        cursor.execute(f"SELECT {first_column}, {second_column} FROM {tablename}")
        records = cursor.fetchall()

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return render_template("error.html", message=f"Table {tablename} does not exist.")
    finally:
        cursor.close()
        conn.close()

    return render_template(
        "list.html",
        records=records,
        tablename=tablename,
        first_column=first_column,
        second_column=second_column
    )


if __name__ == '__main__':
    app.run(debug=True)