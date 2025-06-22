from flask import Flask, render_template, request, redirect, url_for, session, flash
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
mariadb_data_types = [
    # Numeric Data Types
    [
        ["TINYINT", "-128", "127", "1 byte"],
        ["SMALLINT", "-32,768", "32,767", "2 bytes"],
        ["MEDIUMINT", "-8,388,608", "8,388,607", "3 bytes"],
        ["INT", "-2,147,483,648", "2,147,483,647", "4 bytes"],
        ["BIGINT", "-9,223,372,036,854,775,808", "9,223,372,036,854,775,807", "8 bytes"],
        ["DECIMAL", "Depends on precision", "Depends on precision", "Variable"],
        ["FLOAT", "-3.402823466E+38", "3.402823466E+38", "4 bytes"],
        ["DOUBLE", "-1.7976931348623157E+308", "1.7976931348623157E+308", "8 bytes"]
    ],

    # Date and Time Data Types
    [
        ["DATE", "1000-01-01", "9999-12-31", "3 bytes"],
        ["DATETIME", "1000-01-01 00:00:00", "9999-12-31 23:59:59", "8 bytes"],
        ["TIMESTAMP", "1970-01-01 00:00:01 UTC", "2038-01-19 03:14:07 UTC", "4 bytes"],
        ["TIME", "-838:59:59", "838:59:59", "3 bytes"],
        ["YEAR", "1901", "2155", "1 byte"]
    ],

    # String Data Types
    [
        ["CHAR", "1", "255", "1-255 bytes"],
        ["VARCHAR", "1", "65535", "1-65535 bytes"],
        ["TEXT", "1", "65535", "1-65535 bytes"],
        ["TINYTEXT", "1", "255", "1-255 bytes"],
        ["MEDIUMTEXT", "1", "16,777,215", "1-16 MB"],
        ["LONGTEXT", "1", "4,294,967,295", "1-4 GB"],
        ["BLOB", "1", "65535", "1-65535 bytes"],
        ["TINYBLOB", "1", "255", "1-255 bytes"],
        ["MEDIUMBLOB", "1", "16,777,215", "1-16 MB"],
        ["LONGBLOB", "1", "4,294,967,295", "1-4 GB"]
    ],

    # Other Data Types
    [
        ["ENUM", "1", "65,535 values", "1-2 bytes"],
        ["SET", "1", "64 members", "1-8 bytes"],
        ["JSON", "N/A", "N/A", "Variable"]
    ]
]
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "mypassword"),
        database=os.getenv("DB_NAME", "ecom")
    )

@app.context_processor
def inject_tables():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch table names from the database
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name <> 'Admin';")
        tables=cursor.fetchall()
    except mysql.connector.Error as e:
        print(f"Error: {e}")
        tables = []
    finally:
        cursor.close()
        conn.close()

    # Return the tables variable to be globally available in all templates
    return {"tables": tables}


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
    return render_template("base.html", username=session["user"])

def get_FKdata(table):
    Id = table + 'Id'
    Name = table
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(f"SELECT {Name} AS Name, {Id} AS Id FROM {table}")
        data = cursor.fetchall()  # Fully fetch results
    finally:
        cursor.close()
        conn.close()
    return data

def get_metadata(table):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(f"DESCRIBE `{table}`")
        data = cursor.fetchall()
    except mysql.connector.Error as e:
        print(f"Error: {e}")
        data = []
    finally:
        cursor.close()
        conn.close()

    with open("main.txt", "r") as file:
        main_tables = [line.strip() for line in file.readlines()]

    meta = []
    excluded_fields = ['IsDeleted', 'RecordCreationLogin', 'LastUpdationLogin']

    for dt in data:
        if dt['Key'] == 'PRI' or 'datetime' in dt['Type'] or dt['Field'] in excluded_fields:
            continue

        field_name = dt['Field']
        input_type = 'int'

        if 'Is' in dt['Field'] and dt['Type'] == 'varchar(1)':
            input_type = 'radio'
        elif 'varchar' in dt['Type']:
            input_type = 'varchar'
        elif 'text' in dt['Type']:
            input_type = 'textarea'
        elif 'enum' in dt['Type']:
            input_type = 'enum'
            enum_options = dt['Type'].strip('enum()').replace("'", "").split(',')
            meta.append({'name': field_name, 'type': input_type, 'enum_options': enum_options, 'len': len(enum_options), 'FK': None})
            continue

        fk_data = None
        if 'int' in dt['Type']:
            for main_table in main_tables:
                if main_table in field_name:
                    fk_data = get_FKdata(main_table)
                    break

        meta.append({'name': field_name, 'type': input_type, 'FK': fk_data})

    return meta

@app.route("/Entry/<tablename>")
def Entry(tablename):
    try:
        metadata = get_metadata(tablename)
        return render_template('CreateSubmit.html', metadata=metadata, tablename=tablename)
    except Exception as e:
        print(f"Error in Entry route: {e}")
        return render_template("error.html", message=f"An error occurred: {e}")

@app.route("/CreateSubmit/<tablename>", methods=["POST"])
def CreateSubmit(tablename):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        metadata = get_metadata(tablename)
        fields = []
        values = []

        for field in metadata:
            field_name = field["name"]
            field_value = request.form.get(field_name)

            # Handle varchar(1) fields (e.g., radio buttons)
            if field["type"] == "radio":
                field_value = "Y" if field_value == "Y" else "N"

            # Handle foreign key fields
            if field["FK"]:
                fk_data = field["FK"]
                field_value = next((fk["Id"] for fk in fk_data if fk["Name"] == field_value), field_value)

            fields.append(field_name)
            values.append(field_value)

        placeholders = ", ".join(["%s"] * len(fields))
        query = f"INSERT INTO `{tablename}` ({', '.join(fields)}) VALUES ({placeholders})"
        cursor.execute(query, values)
        conn.commit()

        flash("Record created successfully.", "success")
    except mysql.connector.Error as e:
        print(f"Error: {e}")
        flash(f"Error: {e}", "danger")
        return render_template("error.html", message=f"An error occurred: {e}")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('Entry', tablename=tablename))

@app.route("/Update/<tablename>", methods=["GET", "POST"])
def Update(tablename):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    metadata = get_metadata(tablename)
    print(metadata)  # Debugging: Print metadata to check foreign key mappings  
    primary_key_column = f"{tablename}Id"

    if request.method == "POST":
        record_id = request.form.get("primary_key")
        print("Record ID:", record_id)  # Debugging: Check the value of record_id
        cursor.execute(f"SELECT * FROM `{tablename}` WHERE `{primary_key_column}` = %s", (record_id,))
        record = cursor.fetchone()

        # Map foreign key IDs to names for display
        for field in metadata:
            if field["FK"]:
                fk_data = field["FK"]
                record[field["name"]] = next((fk["Name"] for fk in fk_data if fk["Id"] == record[field["name"]]), record[field["name"]])
        print(record)  # Check if foreign key IDs are mapped to names

        cursor.close()
        conn.close()
        return render_template("update.html", metadata=metadata, record=record, tablename=tablename, primary_key_column=primary_key_column, primary_key_value=record_id)

    cursor.execute(f"SELECT `{primary_key_column}`, `{tablename}` FROM `{tablename}`")
    primary_keys = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("update.html", metadata=metadata, primary_keys=primary_keys, tablename=tablename, primary_key_column=primary_key_column)

@app.route("/UpdateSubmit/<tablename>/<record_id>", methods=["POST"])
def UpdateSubmit(tablename, record_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        metadata = get_metadata(tablename)
        updates = []
        values = []

        for field in metadata:
            field_name = field["name"]
            field_value = request.form.get(field_name)

            # Handle varchar(1) fields (e.g., radio buttons)
            if field["type"] == "radio":
                field_value = "Y" if field_value == "Y" else "N"

            # Handle foreign key fields
            if field["FK"]:
                fk_data = field["FK"]
                field_value = next((fk["Id"] for fk in fk_data if fk["Name"] == field_value), field_value)

            updates.append(f"{field_name} = %s")
            values.append(field_value)

        query = f"UPDATE `{tablename}` SET {', '.join(updates)} WHERE `{tablename}Id` = %s"
        values.append(record_id)
        cursor.execute(query, values)
        conn.commit()

        flash("Record updated successfully.", "success")

        cursor.close()
        conn.close()
        return redirect(url_for("Display", tablename=tablename))
    except mysql.connector.Error as e:
        print(f"Error: {e}")
        return render_template("error.html", message=f"An error occurred: {e}")

@app.route("/Delete/<tablename>", methods=["GET", "POST"])
def Delete(tablename):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Dynamically determine the primary key and display column
        primary_key_column = f"{tablename}Id"  # Primary key follows the convention <TableName>Id
        display_column = tablename  # Display column is the same as the table name

        # Fetch all records with IsDeleted = 'N'
        cursor.execute(f"SELECT `{primary_key_column}`, `{display_column}` FROM `{tablename}` WHERE `IsDeleted` = 'N'")
        records = cursor.fetchall()

        # If a record is selected for deletion
        if request.method == "POST":
            record_id = request.form.get("record_id")
            is_deleted = request.form.get("IsDeleted")

            # Map "Yes" to "Y" and "No" to "N"
            is_deleted_value = "Y" if is_deleted == "Yes" else "N"

            # If the user sets IsDeleted to 'Y'
            if is_deleted_value == "Y":
                try:
                    # Update the record to set IsDeleted = %s
                    cursor.execute(f"UPDATE `{tablename}` SET `IsDeleted` = %s WHERE `{primary_key_column}` = %s", (is_deleted_value, record_id))
                    conn.commit()
                    flash("Record marked as deleted successfully.", "success")
                except mysql.connector.Error as e:
                    # Handle foreign key constraint errors
                    if "foreign key constraint" in str(e).lower():
                        flash("Cannot delete record due to foreign key constraints.", "danger")
                    else:
                        flash(f"Error: {e}", "danger")
            else:
                flash("No changes made.", "info")

        # Refresh the records for the dropdown
        cursor.execute(f"SELECT `{primary_key_column}`, `{display_column}` FROM `{tablename}` WHERE `IsDeleted` = 'N'")
        records = cursor.fetchall()

    except mysql.connector.Error as e:
        flash(f"Error: {e}", "danger")
        records = []
        primary_key_column = None
        display_column = None
    finally:
        cursor.close()
        conn.close()

    return render_template("delete.html", tablename=tablename, records=records, primary_key_column=primary_key_column, display_column=display_column)

@app.route("/Undelete/<tablename>", methods=["GET", "POST"])
def Undelete(tablename):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Dynamically determine the primary key and display column
        primary_key_column = f"{tablename}Id"  # Primary key follows the convention <TableName>Id
        display_column = tablename  # Display column is the same as the table name

        # Fetch all records with IsDeleted = 'Y'
        cursor.execute(f"SELECT `{primary_key_column}`, `{display_column}` FROM `{tablename}` WHERE `IsDeleted` = 'Y'")
        records = cursor.fetchall()
        print("Records:", records)  # Debugging: Check fetched records

        # Fetch the details of the selected record
        record_id = request.args.get("record_id")
        
        record_details = None
        if record_id:
            cursor.execute(f"SELECT * FROM `{tablename}` WHERE `{primary_key_column}` = %s", (record_id,))
            record_details = cursor.fetchone()
            
    except mysql.connector.Error as e:
        flash(f"Error: {e}", "danger")
        records = []
        record_details = None
    finally:
        cursor.close()
        conn.close()

    return render_template("undelete.html", tablename=tablename, records=records, record_details=record_details, primary_key_column=primary_key_column, display_column=display_column)

@app.route("/UndeleteSubmit/<tablename>", methods=["POST"])
def UndeleteSubmit(tablename):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Dynamically determine the primary key column
        primary_key_column = f"{tablename}Id"  # Primary key follows the convention <TableName>Id

        # Fetch form data
        record_id = request.form.get("record_id")  # Fetch the selected record ID
        is_deleted = request.form.get("IsDeleted")  # Fetch the IsDeleted value

        # Validate record_id
        if not record_id:
            flash("Please select a record to recover.", "danger")
            return redirect(url_for("Undelete", tablename=tablename))

        # Map "Yes" to "Y" and "No" to "N"
        is_deleted_value = "N" if is_deleted == "No" else "Y"

        # If the user sets IsDeleted to 'N' (recover the record)
        if is_deleted_value == "N":
            try:
                # Update the record to set IsDeleted = 'N'
                cursor.execute(f"UPDATE `{tablename}` SET `IsDeleted` = %s WHERE `{primary_key_column}` = %s", (is_deleted_value, record_id))
                conn.commit()
                flash("Record recovered successfully.", "success")
            except mysql.connector.Error as e:
                flash(f"Error: {e}", "danger")
        else:
            flash("No changes made.", "info")

    except mysql.connector.Error as e:
        flash(f"Error: {e}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("Undelete", tablename=tablename))

@app.route("/Display/<tablename>")
def Display(tablename):
    page = request.args.get("page", 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(f"SELECT * FROM `{tablename}` WHERE `IsDeleted` = 'N' LIMIT %s OFFSET %s", (per_page, offset))
        records = cursor.fetchall()

        metadata = get_metadata(tablename)

        # Map foreign key IDs to names for display
        for record in records:
            for field in metadata:
                if field["FK"]:
                    fk_data = field["FK"]
                    record[field["name"]] = next((fk["Name"] for fk in fk_data if fk["Id"] == record[field["name"]]), record[field["name"]])
        print("Metadata:", metadata)
        print("Records:", records)

        cursor.execute(f"SELECT COUNT(*) AS total FROM `{tablename}` WHERE `IsDeleted` = 'N'")
        total = cursor.fetchone()["total"]

        total_pages = (total // per_page) + (1 if total % per_page > 0 else 0)
    except mysql.connector.Error as e:
        flash(f"Error: {e}", "danger")
        records = []
        total_pages = 0
    finally:
        cursor.close()
        conn.close()

    return render_template("display.html", records=records, tablename=tablename, page=page, total_pages=total_pages,metadata=metadata)

@app.route("/List/<tablename>")
def List(tablename):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch metadata for the table
        metadata = get_metadata(tablename)

        # Determine the primary key and name column
        primary_key_column = f"{tablename}Id"  # Assuming primary key follows this naming convention
        name_column = tablename  # Assuming name column matches the table name

        # Fetch records with the primary key and name column
        cursor.execute(f"SELECT `{primary_key_column}`, `{name_column}` FROM `{tablename}`")
        records = cursor.fetchall()

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        records = []
        primary_key_column = ""
        name_column = ""
    finally:
        cursor.close()
        conn.close()

    return render_template("list.html", records=records, tablename=tablename, first_column=primary_key_column, second_column=name_column)


if __name__ == '__main__':
    app.run(debug=True)