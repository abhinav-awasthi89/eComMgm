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


# users = {
#     "admin": {"password": "password123", "role": "admin"},
#     "user": {"password": "pass123", "role": "user"}
# }
arr=['Entry','Update','Display','List','Delete'] #Crud 


   
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "mypassword"),
        database=os.getenv("DB_NAME", "ecomv1")
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
def logintype():
    if request.method == "POST":
        login_type = request.form.get("login_type")
        session["login_type"] = login_type  # Store the login type in the session

        user=None
        if(login_type=='isAdmin'):
            user="Admin"
        elif(login_type=='isVendor'):
            user="Vendor"
        elif(login_type=='isCourier'):
            user="Courier"
        

        return render_template("login.html", error="Invalid Credentials",user=user)

    return render_template("logintype.html")
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        login_type = session.get("login_type")
        conn= get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM User ")
            data = cursor.fetchall()
            print("Data:", data) 
            user_found = False

            for dt in data:
                if dt['User'] == username and dt['Passwd'] == password:
                    user_found = True
        # Role-based checks
                    if login_type == 'isAdmin' and dt['IsAdmin'] == 'Y' and dt['IsVerified'] == 'Y' and dt['IsActivated'] == 'Y' and dt['IsBlackListed'] == 'N' and dt['IsDead'] == 'N' and dt['IsDeleted'] == 'N':
                        session['user'] = username
                        flash("Login successful!", "success")
                        return redirect(url_for("dashboard"))
                    elif login_type == 'isVendor' and dt['IsVendor'] == 'Y' and dt['IsVerified'] == 'Y' and dt['IsActivated'] == 'Y' and dt['IsBlackListed'] == 'N' and dt['IsDead'] == 'N' and dt['IsDeleted'] == 'N':
                        session['user'] = username
                        flash("Login successful!", "success")
                        return redirect(url_for("dashboard"))
                    elif login_type == 'isCourier' and dt['IsCourier'] == 'Y' and dt['IsVerified'] == 'Y' and dt['IsActivated'] == 'Y' and dt['IsBlackListed'] == 'N' and dt['IsDead'] == 'N' and dt['IsDeleted'] == 'N':
                        session['user'] = username
                        flash("Login successful!", "success")
                        return redirect(url_for("dashboard"))
                    else:
                        flash(f"You are not authorized to login as {login_type[2:]}.", "danger")
                        return render_template("login.html")

            if user_found==False:
                flash("Invalid credentials. Please try again.", "danger")

                    

                        
                    
        except mysql.connector.Error as e:
            print(f"Error: {e}")
        finally:    
            cursor.close()
            conn.close()

        
    return render_template("login.html")

@app.route("/logout")
def logout():
    # Clear the session
    session.clear()
    # Redirect to the login page
    return redirect(url_for("logintype"))

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
        return redirect(url_for("logintype"))
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

        if  dt['Field']=='Gender':
            input_type = 'radio1'
        elif dt['Type']=='char(1)':
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
            if field["type"] == "radio1":
                field_value = "M" if field_value == "M" else "F"

            # Handle foreign key fields
            if field["FK"]:
                fk_data = field["FK"]
                field_value = next((fk["Id"] for fk in fk_data if fk["Name"] == field_value), field_value)

            fields.append(field_name)
            values.append(field_value)

        # Add RecordCreationLogin field
        fields.append("RecordCreationLogin")
        values.append(session.get("login_type", "Unknown"))  # Default to "Unknown" if session['login_type'] is not set

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
    primary_key_column = f"{tablename}Id"
    record=None
    record_id=None

    if request.method == "POST":
        record_id = request.form.get("primary_key")
        print("Record ID:", record_id)  # Debugging: Check the value of record_id
        cursor.execute(f"SELECT * FROM `{tablename}` WHERE `{primary_key_column}` = %s", (record_id,))
        record = cursor.fetchone()

        # Map foreign key IDs to names for display
        for field in metadata:
            if field["FK"]:
                field["FK"] = [{"Name": fk["Name"], "Id": fk["Id"]} for fk in field["FK"]]
                fk_data = field["FK"]
                record[field["name"]] = next((fk["Name"] for fk in fk_data if fk["Id"] == record[field["name"]]), record[field["name"]])
        print(record)
        

    cursor.execute(f"SELECT `{primary_key_column}`, `{tablename}` FROM `{tablename}`")
    primary_keys = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("update.html", metadata=metadata, primary_keys=primary_keys, tablename=tablename, primary_key_column=primary_key_column,record=record,primary_key_value=record_id)

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
            if field["type"] == "radio1":
                field_value = "M" if field_value == "M" else "F"

            # Handle foreign key fields
            if field["FK"]:
                fk_data = field["FK"]
                field_value = next((fk["Id"] for fk in fk_data if fk["Name"] == field_value), field_value)

            updates.append(f"{field_name} = %s")
            values.append(field_value)

        # Add LastUpdationLogin field
        updates.append("LastUpdationLogin = %s")
        values.append(session.get("login_type", "Unknown"))  # Default to "Unknown" if session['login_type'] is not set

        query = f"UPDATE `{tablename}` SET {', '.join(updates)} WHERE `{tablename}Id` = %s"
        values.append(record_id)

        # Debugging
        print(f"Query: {query}")
        print(f"Values: {values}")

        cursor.execute(query, values)
        conn.commit()

        flash("Record updated successfully.", "success")
        return redirect(url_for("Display", tablename=tablename))
    except mysql.connector.Error as e:
        print(f"Error: {e}")
        return render_template("error.html", message=f"An error occurred: {e}")
    finally:
        cursor.close()
        conn.close()

@app.route("/Delete/<tablename>", methods=["GET", "POST"])
def Delete(tablename):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Dynamically determine the primary key and display column
        primary_key_column = f"{tablename}Id"  # Primary key follows the convention <TableName>Id
        display_column = tablename  # Display column is the same as the table name

        # Fetch all records with IsDeleted = 'N'
        cursor.execute(f"SELECT `{primary_key_column}`, `{display_column}` FROM `{tablename}` WHERE `IsDeleted` = 'N' or `IsDeleted` = '' ")
        records = cursor.fetchall()

        # If a record is selected for deletion
        if request.method == "POST":
            record_id = request.form.get("record_id")
            is_deleted = request.form.get("IsDeleted")

            # Map "Yes" to "Y" and "No" to "N"
            is_deleted_value = "Y"  if is_deleted == "Yes" and is_deleted!='' else "N"

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
        cursor.execute(f"SELECT `{primary_key_column}`, `{display_column}` FROM `{tablename}` WHERE `IsDeleted` = 'N' or `IsDeleted` = '' ")
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

        # Initialize record_details
        record_details = None

        # Handle POST request to load record details
        if request.method == "POST":
            record_id = request.form.get("record_id")  # Fetch the selected record ID
            if record_id:
                cursor.execute(f"SELECT * FROM `{tablename}` WHERE `{primary_key_column}` = %s", (record_id,))
                record_details = cursor.fetchone()
                print("Record Details:", record_details)  # Debugging: Check fetched record details
            else:
                flash("Please select a valid record.", "danger")

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

        
        record_id = request.args.get("record_id") 
        print("Recovered record_id",record_id)
        

        
        try:
            print("did controll")
            cursor.execute(f"UPDATE `{tablename}` SET `IsDeleted` = 'N' WHERE `{primary_key_column}` = %s", (record_id,))
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
        cursor.execute(f"SELECT * FROM `{tablename}` WHERE `IsDeleted` = 'N' or `IsDeleted`=''LIMIT %s OFFSET %s", (per_page, offset))
        records = cursor.fetchall()

        metadata = get_metadata(tablename)

        # Map foreign key IDs to names for display
        for record in records:
            for field in metadata:
                if field["FK"]:
                    fk_data = field["FK"]
                    record[field["name"]] = next((fk["Name"] for fk in fk_data if fk["Id"] == record[field["name"]]), record[field["name"]])
       
        cursor.execute(f"SELECT COUNT(*) AS total FROM `{tablename}` WHERE `IsDeleted` = 'N' or `IsDeleted` = ''")
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

@app.route("/List/<tablename>", methods=["GET"])
def List(tablename):
    conn = get_db_connection()  # Connect to the database
    cursor = conn.cursor(dictionary=True)  # Create a cursor to execute queries
    try:
        # Define the primary key and name column
        primary_key_column = f"{tablename}Id"  # Primary key column (e.g., "tablenameId")
        name_column = tablename  # Name column (e.g., "tablename")

        # Get pagination and search parameters from the URL
        page = request.args.get("page", 1, type=int)  # Current page number (default is 1)
        per_page = 10  # Number of records per page
        offset = (page - 1) * per_page  # Calculate the starting point for records
        search_query = request.args.get("search", "").strip()  # Search query (default is empty)

        # Base query to fetch records
        query = f"SELECT `{primary_key_column}`, `{name_column}` FROM `{tablename}`"
        count_query = f"SELECT COUNT(*) AS total FROM `{tablename}`"

        # Add search filter if a search query is provided
        if search_query:
            query += f" WHERE `{name_column}` LIKE %s"
            count_query += f" WHERE `{name_column}` LIKE %s"
            search_param = f"%{search_query}%"  # Add wildcards for partial matching
            cursor.execute(query + f" LIMIT %s OFFSET %s", (search_param, per_page, offset))
            records = cursor.fetchall()  # Fetch the filtered records
            cursor.execute(count_query, (search_param,))
        else:
            cursor.execute(query + f" LIMIT %s OFFSET %s", (per_page, offset))
            records = cursor.fetchall()  # Fetch the records without filtering
            cursor.execute(count_query)

        total = cursor.fetchone()["total"]  # Get the total number of records
        total_pages = (total // per_page) + (1 if total % per_page > 0 else 0)  # Calculate total pages

    except mysql.connector.Error as err:
        print(f"Error: {err}")  # Print any database errors
        records = []  # Default to an empty list if an error occurs
        total_pages = 0  # Default to 0 pages if an error occurs
        search_query = ""  # Default to an empty search query
    finally:
        cursor.close()  # Close the cursor
        conn.close()  # Close the database connection

    # Render the template with the records, pagination, and search query
    return render_template(
        "list.html",
        records=records,
        tablename=tablename,
        first_column=primary_key_column,
        second_column=name_column,
        page=page,
        total_pages=total_pages,
        search_query=search_query
    )


if __name__ == '__main__':
    app.run(debug=True)