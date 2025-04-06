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
        database=os.getenv("DB_NAME", "ecom")
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
    cursor.close()
    conn.close()

    # Read main tables from main.txt
    with open("main.txt", "r") as file:
        main_tables = [line.strip().lower() for line in file.readlines()]

    meta = []

    # Check if the table is in main_tables
    if table.lower() in main_tables:
        # Process metadata for main tables
        for dt in data:
            if dt['Key'] == 'PRI' or 'datetime' in dt['Type']:
                continue

            field_name = dt['Field']
            input_type = 'varchar' if 'varchar' in dt['Type'] else 'int'
            meta.append({'name': field_name, 'type': input_type, 'FK': None})
    else:
        # Process metadata for non-main tables
        for dt in data:
            if dt['Key'] == 'PRI' or 'datetime' in dt['Type']:
                continue

            field_name = dt['Field']
            input_type = 'varchar'  # Default to varchar for text fields
            fk_data = None

            # Check if the column is a foreign key referencing a main table
            if 'int' in dt['Type']:
                input_type = 'int'
                for main_table in main_tables:
                    if main_table.lower() in field_name.lower():
                        print(f"I am here, with values mainTable: {main_table} and field: {field_name}")
                        # Extract the primary key column of the main table
                        conn = get_db_connection()
                        cursor = conn.cursor(dictionary=True)
                        cursor.execute(f"DESCRIBE {main_table}")
                        main_table_metadata = cursor.fetchall()
                        cursor.close()
                        conn.close()

                        main_table_primary_key = None
                        for field in main_table_metadata:
                            if field["Key"] == "PRI":
                                main_table_primary_key = field["Field"]
                                break

                        # If the column matches the primary key of the main table
                        if main_table_primary_key and main_table_primary_key.lower() in field_name.lower():
                            input_type = 'dropdown'
                            conn = get_db_connection()
                            cursor = conn.cursor(dictionary=True)
                            cursor.execute(f"SELECT {main_table_primary_key} AS Id, {main_table} AS Name FROM {main_table}")
                            fk_data = cursor.fetchall()
                            cursor.close()
                            conn.close()
                            break

                        elif field_name.lower() in main_table_primary_key.lower():
                            input_type = 'dropdown'
                            conn = get_db_connection()
                            cursor = conn.cursor(dictionary=True)
                            cursor.execute(f"SELECT {main_table_primary_key} AS Id, {main_table} AS Name FROM {main_table}")
                            fk_data = cursor.fetchall()
                            cursor.close()
                            conn.close()
                            break

            elif 'enum' in dt['Type']:
                input_type = 'enum'
                enum_options = dt['Type'].strip('enum()').replace("'", "").split(',')
                meta.append({'name': field_name, 'type': input_type, 'enum_options': enum_options})
                continue

            meta.append({'name': field_name, 'type': input_type, 'FK': fk_data})

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
    try:
        # Read the main tables from main.txt
        with open("main.txt", "r") as file:
            main_tables = [line.strip().lower() for line in file.readlines()]

        cursor.execute(f"DESCRIBE {tablename}")
        data = cursor.fetchall()

        fields = [] 
        values = []
        excluded_fields = ['IsDeleted', 'RecordCreationLogin', 'LastUpdationTimeStamp', 'LastUpdationLogin']

        for dt in data:
            if dt['Key'] == 'PRI' or 'datetime' in dt['Type'] or dt['Field'] in excluded_fields:
                continue

            field_name = dt['Field']
            field_value = request.form.get(field_name)

            # Debugging: Check if the field and value are being processed
            print(f"Processing field: {field_name}, value: {field_value}")

            # # Validate the Brand field
            # if field_name == "Brand" and not field_value:
            #     return render_template("error.html", message="Brand field cannot be empty.")

            # Add the field and value to the main table insertion
            fields.append(field_name)
            values.append(field_value)

        # Debugging: Print the fields and values
        print("Fields:", fields)
        print("Values:", values)

        # Insert the main record into the table
        placeholders = ", ".join(["%s"] * len(fields))
        query = f"INSERT INTO {tablename} ({', '.join(fields)}) VALUES ({placeholders})"
        cursor.execute(query, values)
        conn.commit()

    except mysql.connector.Error as e:
        print(f"Error: {e}")
        return render_template("error.html", message=f"An error occurred: {e}")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('Entry', tablename=tablename))

@app.route("/Update/<tablename>", methods=["GET", "POST"])
def Update(tablename):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(f"DESCRIBE {tablename}")
    metadata = cursor.fetchall()

    # Find the primary key column
    primary_key_column = None
    for field in metadata:
        if field["Key"] == "PRI":
            primary_key_column = field["Field"]
            break

    if request.method == "POST":
        # Fetch the selected record based on the primary key value
        record_id = request.form.get("primary_key")
        cursor.execute(f"SELECT * FROM {tablename} WHERE {primary_key_column} = %s", (record_id,))
        record = cursor.fetchone()
        cursor.close()
        conn.close()
        return render_template("update.html", metadata=metadata, record=record, tablename=tablename, primary_key_column=primary_key_column, primary_key_value=record_id)

    # Fetch all primary key values for the dropdown
    cursor.execute(f"SELECT {primary_key_column} FROM {tablename}")
    primary_keys = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("update.html", metadata=metadata, primary_keys=primary_keys, tablename=tablename, primary_key_column=primary_key_column)

@app.route("/UpdateSubmit/<tablename>/<record_id>", methods=["POST"])
def UpdateSubmit(tablename, record_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)  # Use dictionary=True for the cursor
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
        return redirect(url_for("Display", tablename=tablename))
    except mysql.connector.Error as e:
        print(f"Error: {e}")
        return render_template("error.html", message=f"An error occurred: {e}")

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
        # if len(columns) < 2:
        #     return render_template("error.html", message=f"Table {tablename} does not have enough columns.")

        first_column = columns[0]["Field"]
        second_column = columns[1]["Field"]

        # Fetch data for the first two columns
        cursor.execute(f"SELECT {first_column}, {second_column} FROM {tablename}")
        records = cursor.fetchall()

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        # return render_template("error.html", message=f"Table {tablename} does not exist.")
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