import os
import re
import logging
from dotenv import load_dotenv
from datetime import datetime
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    send_from_directory,
    jsonify,
    abort
)
from flask_mail import Mail, Message
from database.db import get_db_connection
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

# =========================================
# FLASK APP
# =========================================

app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv("SECRET_KEY")
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_USERNAME")

mail = Mail(app)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

# =========================================
# PDF FOLDER
# =========================================

if not os.path.exists("pdfs"):
    os.makedirs("pdfs")

# =========================================
# LOGIN
# =========================================

@app.route('/login', methods=['GET', 'POST'])
def login():

    db, cursor = get_db_connection()

    try:

        if request.method == 'POST':

            username = request.form['username']
            password = request.form['password']

            cursor.execute("""
                SELECT *
                FROM users
                WHERE username=%s
            """, (username,))

            user = cursor.fetchone()

            if user and check_password_hash(user['password'], password):

                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                session['emp_name'] = user['emp_name']
                session['emp_id'] = user['emp_id']
                session['email'] = user['email']

                return redirect('/')

            return "Invalid Login"

        return render_template('login.html')

    finally:

        cursor.close()
        db.close()


# =========================================
# SIGNUP
# =========================================

@app.route('/signup', methods=['GET', 'POST'])
def signup():

    db, cursor = get_db_connection()

    try:

        if request.method == 'POST':

            # FORM DATA

            emp_name = request.form['emp_name']

            username = request.form['username']

            password = request.form['password']

            hashed_password = generate_password_hash(password)

            email = request.form['email']

            # FETCH EMPLOYEE DETAILS FROM DATABASE

            cursor.execute("""
                SELECT *
                FROM employees
                WHERE UPPER(emp_name)=UPPER(%s)
            """, (emp_name,))

            employee = cursor.fetchone()

            # IF EMPLOYEE NOT FOUND

            if not employee:

                return "Employee not found in database"

            # FETCH EMPLOYEE ID

            emp_id = employee['emp_id']

            # CHECK IF EMPLOYEE ALREADY REGISTERED

            cursor.execute("""
                SELECT *
                FROM users
                WHERE emp_id=%s
            """, (emp_id,))

            existing_employee = cursor.fetchone()

            if existing_employee:

                return "Employee already registered"

            # CHECK EXISTING USERNAME

            cursor.execute("""
                SELECT *
                FROM users
                WHERE username=%s
            """, (username,))

            existing_user = cursor.fetchone()

            if existing_user:

                return "Username already exists"
            cursor.execute("""
                SELECT *
                FROM users
                WHERE email=%s
            """, (email,))

            existing_email = cursor.fetchone()

            if existing_email:
                return "Email already exists"
            # INSERT USER

            cursor.execute("""
                INSERT INTO users
                (
                    emp_id,
                    emp_name,
                    username,
                    password,
                    role,
                    email
                )
                VALUES
                (%s,%s,%s,%s,%s,%s)
            """, (
                emp_id,
                emp_name,
                username,
                hashed_password,
                'employee',
                email
            ))

            db.commit()

            return redirect('/login')

        return render_template('signup.html')

    finally:

        cursor.close()
        db.close()

# =========================================
# LOGOUT
# =========================================

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/login')


# =========================================
# DASHBOARD
# =========================================

@app.route('/')
def index():

    if 'username' not in session:
        return redirect('/login')

    db, cursor = get_db_connection()

    try:

        cursor.execute("""
            SELECT *
            FROM regions
            ORDER BY region_name
        """)

        regions = cursor.fetchall()

        return render_template(
            'index.html',
            regions=regions
        )

    finally:

        cursor.close()
        db.close()


# =========================================
# REGION PAGE
# =========================================

@app.route('/region/<int:region_id>')
def region(region_id):

    if 'username' not in session:
        return redirect('/login')

    db, cursor = get_db_connection()

    try:

        cursor.execute("""
            SELECT *
            FROM regions
            WHERE id=%s
        """, (region_id,))

        region = cursor.fetchone()
        if not region:
            abort(404)
        cursor.execute("""
            SELECT *
            FROM substations
            WHERE region_id=%s
            ORDER BY substation_name
        """, (region_id,))

        substations = cursor.fetchall()

        return render_template(
            'region.html',
            region=region,
            substations=substations
        )

    finally:

        cursor.close()
        db.close()


# =========================================
# NEW REQUEST
# =========================================

@app.route('/new-request')
def new_request():

    if 'username' not in session:
        return redirect('/login')

    db, cursor = get_db_connection()

    try:

        cursor.execute("""
            SELECT *
            FROM substations
            ORDER BY substation_name
        """)

        sites = cursor.fetchall()

        cursor.execute("""
            SELECT *
            FROM projects
            ORDER BY project_name
        """)

        projects = cursor.fetchall()

        employee_data = {
            "emp_id": session['emp_id'],
            "emp_name": session['emp_name']
        }

        return render_template(
            'new_request.html',
            sites=sites,
            projects=projects,
            employee_data=employee_data
        )

    finally:

        cursor.close()
        db.close()

# =========================================
# SUBMIT REQUEST
# =========================================

@app.route('/submit', methods=['POST'])
def submit():

    if 'username' not in session:
        return redirect('/login')
    db, cursor = get_db_connection()
    try:

        # =========================================
        # FORM DATA
        # =========================================

        emp_id = request.form.get('emp_id')
        emp_name = request.form.get('emp_name')

        project_name = request.form.get('project_name')
        site_name = request.form.get('site_name')

        if site_name == "CUSTOM":
            site_name = request.form.get('custom_site')
            if not site_name:
                return "Please enter custom site name"

        request_date = request.form.get('request_date')
        departure_date = request.form.get('departure_date')
        return_date = request.form.get('return_date')

        total_days = request.form.get('total_days')

        period_name = request.form.get('period_name')
        quarter = request.form.get('quarter_name')

        purpose = request.form.get('purpose')
        reason_text = request.form.get('reason_text')

        amount_requested = request.form.get('amount_requested')

        # =========================================
        # GET SUBSTATION ID
        # =========================================

        cursor.execute("""
            SELECT id
            FROM substations
            WHERE substation_name=%s
        """, (site_name,))

        substation = cursor.fetchone()
        if substation:
            substation_id = substation['id']
        else:
            cursor.execute("""
                INSERT INTO substations
                (
                    substation_name,
                    region_id
                )
                VALUES(%s,%s)
            """, (
                site_name,
                1
            ))

            db.commit()

            substation_id = cursor.lastrowid

        # =========================================
        # GENERATED LINK
        # =========================================
        if purpose == "CAMC":
            purpose_code = "CAMC"

        elif purpose == "Downcall":
            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM travel_requests
                WHERE emp_id=%s
                AND purpose='Downcall'
                AND period_name=%s
            """, (
                emp_id,
                period_name
            ))
            downcall_count = cursor.fetchone()['total'] + 1

            purpose_code = f"D{downcall_count}"

        elif purpose == "Installation":
            purpose_code = "INST"

        elif purpose == "Maintenance":
            purpose_code = "MAIN"
        else:
            purpose_code = purpose

        generated_link = (
            f"{project_name}/"
            f"{period_name}/"
            f"{site_name}/"
            f"{purpose_code}/"
            f"{quarter}"
        )

        # =========================================
        # PDF GENERATION
        # =========================================

        safe_filename = (
            generated_link.replace('/', '_')
            + f"_{emp_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )

        safe_filename = re.sub(
            r'[^A-Za-z0-9_-]',
            '_',
            safe_filename
        )
        pdf_filename = safe_filename + ".pdf"
        pdf_path = os.path.join(
            "pdfs",
            pdf_filename
        )

        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=letter
        )

        styles = getSampleStyleSheet()

        elements = []

        # =========================================
        # TITLE
        # =========================================

        title = Paragraph(
            "<b>Travel Expense Claim Sheet</b>",
            styles['Title']
        )

        elements.append(title)

        elements.append(Spacer(1, 20))

        # =========================================
        # DETAILS TABLE
        # =========================================

        details = [

            ['Employee Name', emp_name],
            ['Employee ID', emp_id],
            ['Project', project_name],
            ['Site', site_name],
            ['Request Date', request_date],
            ['Departure Date', departure_date],
            ['Return Date', return_date],
            ['Total Days', total_days],
            ['Period', period_name],
            ['Quarter', quarter],
            ['Purpose', purpose],
            ['Reason', reason_text]

        ]

        details_table = Table(
            details,
            colWidths=[200, 300]
        )

        details_table.setStyle(TableStyle([

            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10)

        ]))

        elements.append(details_table)

        elements.append(Spacer(1, 20))

        # =========================================
        # TRAVEL TABLE
        # =========================================

        travel_data = [[
            'Date',
            'From',
            'To',
            'Mode',
            'Persons',
            'Amount'
        ]]

        travel_dates = request.form.getlist('travel_date[]')
        travel_froms = request.form.getlist('travel_from[]')
        travel_tos = request.form.getlist('travel_to[]')
        travel_modes = request.form.getlist('travel_mode[]')
        travel_persons = request.form.getlist('travel_persons[]')
        travel_amounts = request.form.getlist('travel_amount[]')

        for i in range(len(travel_dates)):
            if not travel_dates[i]:
                continue

            travel_data.append([

                travel_dates[i],
                travel_froms[i],
                travel_tos[i],
                travel_modes[i],
                travel_persons[i],
                travel_amounts[i]

            ])     

        elements.append(
            Paragraph(
                "<b>Travelling Expenses</b>",
                styles['Heading2']
            )
        )

        travel_table = Table(travel_data)

        travel_table.setStyle(TableStyle([

            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 9)

        ]))

        elements.append(travel_table)

        elements.append(Spacer(1, 20))

        # =========================================
        # ACCOMMODATION TABLE
        # =========================================

        acc_data = [[
            'From',
            'To',
            'Stay At',
            'Persons',
            'Total Days',
            'Initial Amount',
            'Total Amount'
        ]]

        acc_froms = request.form.getlist('acc_from[]')
        acc_tos = request.form.getlist('acc_to[]')
        acc_stays = request.form.getlist('acc_stay[]')
        acc_persons = request.form.getlist('acc_persons[]')
        acc_days = request.form.getlist('acc_days[]')
        acc_initials = request.form.getlist('acc_initial[]')
        acc_amounts = request.form.getlist('acc_amount[]')

        for i in range(len(acc_froms)):
            if not acc_froms[i]:
                continue

            acc_data.append([
                acc_froms[i],
                acc_tos[i],
                acc_stays[i],
                acc_persons[i],
                acc_days[i],
                acc_initials[i],
                acc_amounts[i]
            ])
        elements.append(
            Paragraph(
                "<b>Accommodation Expenses</b>",
                styles['Heading2']
            )
        )
        acc_table = Table(acc_data)
        acc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 9)
            ]))
        elements.append(acc_table)
        elements.append(Spacer(1, 20))

        # =========================================
        # BOARDING TABLE
        # =========================================

        boarding_data = [[
            'From',
            'To',
            'Total Days',
            'Initial Amount',
            'Total Amount'
        ]]

        board_froms = request.form.getlist('boarding_from[]')
        board_tos = request.form.getlist('boarding_to[]')
        board_days = request.form.getlist('boarding_days[]')
        board_initials = request.form.getlist('boarding_initial[]')
        board_amounts = request.form.getlist('boarding_amount[]')
        for i in range(len(board_froms)):
            if not board_froms[i]:
                continue

            boarding_data.append([

                board_froms[i],
                board_tos[i],
                board_days[i],
                board_initials[i],
                board_amounts[i]

            ])
        elements.append(
            Paragraph(
                "<b>Boarding Expenses</b>",
                styles['Heading2']
            )
        )
        boarding_table = Table(boarding_data)
        boarding_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 9)
            ]))

        elements.append(boarding_table)

        elements.append(Spacer(1, 20))

        # =========================================
        # CONVEYANCE TABLE
        # =========================================

        conveyance_data = [[
            'From',
            'To',
            'Total Days',
            'Initial Amount',
            'Total Amount'
        ]]

        conv_froms = request.form.getlist('conveyance_from[]')
        conv_tos = request.form.getlist('conveyance_to[]')
        conv_days = request.form.getlist('conveyance_days[]')
        conv_initials = request.form.getlist('conveyance_initial[]')
        conv_amounts = request.form.getlist('conveyance_amount[]')

        for i in range(len(conv_froms)):
            if not conv_froms[i]:
                continue

            conveyance_data.append([

                conv_froms[i],
                conv_tos[i],
                conv_days[i],
                conv_initials[i],
                conv_amounts[i]

            ])
        elements.append(
            Paragraph(
                "<b>Conveyance Expenses</b>",
                styles['Heading2']
            )
        )
        conveyance_table = Table(conveyance_data)
        conveyance_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 9)
            ]))
        elements.append(conveyance_table)
        elements.append(Spacer(1, 20))

        # =========================================
        # PER DIEM TABLE
        # =========================================
        per_diem_data = [[
            'From',
            'To',
            'Total Days',
            'Persons',
            'Initial Amount',
            'Total Amount'
        ]]


        pd_froms = request.form.getlist('perdiem_from[]')
        pd_tos = request.form.getlist('perdiem_to[]')
        pd_days = request.form.getlist('perdiem_days[]')
        pd_initials = request.form.getlist('perdiem_initial[]')
        pd_amounts = request.form.getlist('perdiem_amount[]')
        pd_persons = request.form.getlist('perdiem_persons[]')

        for i in range(len(pd_froms)):
            if not pd_froms[i]:
                continue

            per_diem_data.append([
                pd_froms[i],
                pd_tos[i],
                pd_days[i],
                pd_persons[i],
                pd_initials[i],
                pd_amounts[i]
            ])
        elements.append(
            Paragraph(
                "<b>Per Diem Expenses</b>",
                styles['Heading2']
                )
            )
        pd_table = Table(per_diem_data)
        pd_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 9)
        ]))
        elements.append(pd_table)
        elements.append(Spacer(1, 20))

        # =========================================
        # FINAL AMOUNT
        # =========================================

        final_table = Table([

            ['TOTAL AMOUNT REQUESTED', f'₹ {amount_requested}']

        ], colWidths=[300, 200])

        final_table.setStyle(TableStyle([

            ('BACKGROUND', (0, 0), (-1, -1), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12)

        ]))

        elements.append(final_table)

        doc.build(elements)

        # =========================================
        # INSERT DATABASE
        # =========================================

        cursor.execute("""
            INSERT INTO travel_requests
            (
                       emp_id,
                       emp_name,
                       project_name,
                       site_name,
                       substation_id,
                       request_date,
                       departure_date,
                       return_date,
                       total_days,
                       period_name,
                       quarter,
                       purpose,
                       reason_text,
                       generated_link,
                       pdf_file,
                       status,
                       admin_approval,
                       ceo_approval
            )
            VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (

            emp_id,
            emp_name,
            project_name,
            site_name,
            substation_id,
            request_date,
            departure_date,
            return_date,
            total_days,
            period_name,
            quarter,
            purpose,
            reason_text,
            generated_link,
            pdf_filename,
            'Pending',
            'Pending',
            'Pending'

        ))

        db.commit()

        return render_template(
            'submitted.html',
            generated_link=generated_link
        )

    except Exception as e:
        logging.error(f"SUBMIT ERROR: {str(e)}")
        return "Something went wrong"
    finally:
        cursor.close()
        db.close()

# =========================================
# PROFILE
# =========================================

@app.route('/profile')
def profile():

    if 'username' not in session:
        return redirect('/login')

    db, cursor = get_db_connection()

    try:

        cursor.execute("""
            SELECT *
            FROM travel_requests
            WHERE emp_name=%s
            ORDER BY id DESC
        """, (session['emp_name'],))

        requests_data = cursor.fetchall()

        return render_template(
            'profile.html',
            requests_data=requests_data
        )

    finally:

        cursor.close()
        db.close()


# =========================================
# HISTORY
# =========================================

@app.route('/history')
def history():

    if 'username' not in session:
        return redirect('/login')

    db, cursor = get_db_connection()

    try:

        # ADMIN CAN SEE EMPLOYEE REQUESTS

        if session['role'] == 'admin':

            cursor.execute("""
                SELECT *
                FROM travel_requests
                WHERE admin_approval IN ('Pending', 'Query')
                ORDER BY id DESC
            """)

        # CEO CAN SEE ONLY ADMIN APPROVED

        elif session['role'] == 'ceo':

            cursor.execute("""
                SELECT *
                FROM travel_requests
                WHERE admin_approval='Approved'
                AND ceo_approval IN ('Pending', 'Query')
                ORDER BY id DESC
            """)

        else:

            abort(403)

        requests_data = cursor.fetchall()

        return render_template(
            'history.html',
            requests_data=requests_data
        )

    finally:

        cursor.close()
        db.close()
# =========================================
# ANALYTICS
# =========================================

@app.route('/analytics')
def analytics():

    if 'username' not in session:
        return redirect('/login')

    if session['role'] not in ['admin', 'ceo']:
        abort(403)

    db, cursor = get_db_connection()

    try:

        # TOTAL REQUESTS

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM travel_requests
        """)

        total_requests = cursor.fetchone()['total']

        # APPROVED REQUESTS

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM travel_requests
            WHERE status='Approved'
        """)

        approved_requests = cursor.fetchone()['total']

        # PENDING REQUESTS

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM travel_requests
            WHERE status='Pending'
        """)

        pending_requests = cursor.fetchone()['total']

        cursor.execute("""
            SELECT DISTINCT emp_name
            FROM travel_requests
            ORDER BY emp_name
        """)

        employees = cursor.fetchall()
        return render_template(
            'analytics.html',
            total_requests=total_requests,
            approved_requests=approved_requests,
            pending_requests=pending_requests,
            employees=employees
        )

    finally:

        cursor.close()
        db.close()

@app.route('/analytics-data')
def analytics_data():

    if 'username' not in session:
        return jsonify({"error": "Unauthorized"})

    if session['role'] not in ['admin', 'ceo']:
        return jsonify({"error": "Access Denied"})

    db, cursor = get_db_connection()

    try:

        # =========================================
        # FILTER VALUES
        # =========================================

        employee = request.args.get('employee', 'ALL')
        purpose = request.args.get('purpose', 'ALL')

        chart_type = request.args.get('chart_type', 'monthly')

        pie_filter = request.args.get('pie_filter', '')

        line_chart_type = request.args.get(
            'line_chart_type',
            'monthly'
        )

        # =========================================
        # WHERE CONDITIONS
        # =========================================

        conditions = ["status='Approved'"]

        values = []

        if employee != "ALL":

            conditions.append("emp_name=%s")

            values.append(employee)

        if purpose != "ALL":

            conditions.append("purpose=%s")

            values.append(purpose)

        where_clause = " AND ".join(conditions)

        # =========================================
        # BAR CHART
        # =========================================

        if chart_type == "yearly":
            cursor.execute(f"""
                SELECT
                    YEAR(request_date) AS label,
                    COUNT(*) AS total
                FROM travel_requests
                WHERE {where_clause}
                GROUP BY YEAR(request_date)
                ORDER BY YEAR(request_date)
            """, values)

        else:

            cursor.execute(f"""
                SELECT
                    MONTH(request_date) AS month_number,
                    MONTHNAME(request_date) AS label,
                    COUNT(*) AS total
                FROM travel_requests
                WHERE {where_clause}
                GROUP BY
                    MONTH(request_date),
                    MONTHNAME(request_date)
                ORDER BY month_number
            """, values)

        bar_data = cursor.fetchall()

        # =========================================
        # PIE CHART
        # =========================================

        pie_conditions = conditions.copy()

        pie_values = values.copy()

        if chart_type == "yearly" and pie_filter:

            pie_conditions.append("YEAR(request_date)=%s")

            pie_values.append(pie_filter)

        elif chart_type == "monthly" and pie_filter:

            pie_conditions.append("MONTHNAME(request_date)=%s")

            pie_values.append(pie_filter)

        pie_where = " AND ".join(pie_conditions)

        cursor.execute(f"""
            SELECT
                site_name,
                COUNT(*) AS total
            FROM travel_requests
            WHERE {pie_where}
            GROUP BY site_name
            ORDER BY total DESC
        """, pie_values)

        pie_data = cursor.fetchall()

        # =========================================
        # LINE CHART
        # =========================================

        if line_chart_type == "yearly":

            cursor.execute(f"""
                SELECT
                    YEAR(request_date) AS label,
                    COUNT(*) AS total
                FROM travel_requests
                WHERE {where_clause}
                GROUP BY YEAR(request_date)
                ORDER BY YEAR(request_date)
            """, values)

        else:

            cursor.execute(f"""
                SELECT
                    MONTH(request_date) AS month_number,
                    MONTHNAME(request_date) AS label,
                    COUNT(*) AS total
                FROM travel_requests
                WHERE {where_clause}
                GROUP BY
                    MONTH(request_date),
                    MONTHNAME(request_date)
                ORDER BY month_number
            """, values)

        line_data = cursor.fetchall()

        # =========================================
        # EMPLOYEE PURPOSE COUNTS
        # =========================================

        purpose_conditions = conditions.copy()

        purpose_values = values.copy()

        cursor.execute(f"""
            SELECT
                purpose,
                COUNT(*) AS total
            FROM travel_requests
            WHERE {' AND '.join(purpose_conditions)}
            GROUP BY purpose
            ORDER BY purpose
        """, purpose_values)

        purpose_data = cursor.fetchall()

        employee_purpose_counts = {}

        for row in purpose_data:
            employee_purpose_counts[row['purpose']] = row['total']

        # =========================================
        # SITE COUNTS
        # =========================================

        site_conditions = conditions.copy()

        site_values = values.copy()
        cursor.execute(f"""
            SELECT
                site_name,
                COUNT(*) AS total
            FROM travel_requests
            WHERE {' AND '.join(site_conditions)}
            GROUP BY site_name
            ORDER BY total DESC
        """, site_values)

        site_data = cursor.fetchall()

        site_counts = {}

        for row in site_data:
            site_counts[row['site_name']] = row['total']

        # =========================================
        # RETURN JSON
        # =========================================

        return jsonify({

            "bar_labels":
                [row['label'] for row in bar_data],

            "bar_values":
                [row['total'] for row in bar_data],

            "pie_labels":
                [row['site_name'] for row in pie_data],

            "pie_values":
                [row['total'] for row in pie_data],

            "line_labels":
                [row['label'] for row in line_data],

            "line_values":
                [row['total'] for row in line_data],

            "employee_purpose_counts":
                employee_purpose_counts,

            "site_counts":
                site_counts

        })
    except Exception as e:

        logging.error(f"ANALYTICS ERROR: {str(e)}")

        return jsonify({
            "error": "Something went wrong"
        })
    finally:
        cursor.close()
        db.close()
# =====================================
# SETTINGS PAGE
# =====================================

@app.route('/settings')
def settings():

    if 'username' not in session:
        return redirect('/login')

    # ONLY ADMIN + CEO

    if session['role'] not in ['admin', 'ceo']:
        abort(403)

    db, cursor = get_db_connection()

    try:

        # REGIONS

        cursor.execute("""
            SELECT *
            FROM regions
            ORDER BY region_name
        """)

        regions = cursor.fetchall()

        # PROJECTS

        cursor.execute("""
            SELECT *
            FROM projects
            ORDER BY project_name
        """)

        projects = cursor.fetchall()

        # SUBSTATIONS

        cursor.execute("""
            SELECT *
            FROM substations
            ORDER BY substation_name
        """)

        substations = cursor.fetchall()

        # EMPLOYEES

        cursor.execute("""
            SELECT *
            FROM users
            ORDER BY emp_name
        """)

        employees = cursor.fetchall()

        return render_template(
            'settings.html',
            regions=regions,
            projects=projects,
            substations=substations,
            employees=employees
        )

    finally:

        cursor.close()
        db.close()


# =========================================
# ADD REGION
# =========================================

@app.route('/add-region', methods=['POST'])
def add_region():

    if 'username' not in session:
        return redirect('/login')

    if session['role'] not in ['admin', 'ceo']:
        abort(403)

    db, cursor = get_db_connection()

    try:

        region_name = request.form['region_name']

        cursor.execute("""
            INSERT INTO regions(region_name)
            VALUES(%s)
        """, (region_name,))

        db.commit()

        return redirect('/settings')

    finally:

        cursor.close()
        db.close()


# =========================================
# ADD PROJECT
# =========================================

@app.route('/add-project', methods=['POST'])
def add_project():

    if 'username' not in session:
        return redirect('/login')

    if session['role'] not in ['admin', 'ceo']:
        abort(403)

    db, cursor = get_db_connection()

    try:

        project_name = request.form['project_name']

        cursor.execute("""
            INSERT INTO projects(project_name)
            VALUES(%s)
        """, (project_name,))

        db.commit()

        return redirect('/settings')

    finally:

        cursor.close()
        db.close()
# =========================================
# ADD EMPLOYEE
# =========================================

@app.route('/add-employee', methods=['POST'])
def add_employee():

    if 'username' not in session:
        return redirect('/login')

    if session['role'] not in ['admin', 'ceo']:
        abort(403)

    db, cursor = get_db_connection()

    try:

        emp_id = request.form['emp_id']

        emp_name = request.form['emp_name']

        cursor.execute("""
            INSERT INTO employees
            (
                emp_id,
                emp_name
            )
            VALUES(%s,%s)
        """, (
            emp_id,
            emp_name
        ))

        db.commit()

        return redirect('/settings')

    finally:

        cursor.close()
        db.close()
# =========================================
# ADD SITE
# =========================================

@app.route('/add-site', methods=['POST'])
def add_site():

    if 'username' not in session:
        return redirect('/login')

    if session['role'] not in ['admin', 'ceo']:
        abort(403)

    db, cursor = get_db_connection()

    try:

        site_name = request.form['site_name']

        region_id = request.form['region_id']

        cursor.execute("""
            INSERT INTO substations
            (
                substation_name,
                region_id
            )
            VALUES(%s,%s)
        """, (
            site_name,
            region_id
        ))

        db.commit()

        return redirect('/settings')

    finally:

        cursor.close()
        db.close()


# =========================================
# DOWNLOAD PDF
# =========================================

@app.route('/download-pdf/<path:filename>')
def download_pdf(filename):
    if 'username' not in session:
        return redirect('/login')
    return send_from_directory(
        'pdfs',
        filename,
        as_attachment=True
    )


# =========================================
# SUBSTATION PAGE
# =========================================

@app.route('/substation/<int:substation_id>')
def substation(substation_id):

    if 'username' not in session:
        return redirect('/login')

    db, cursor = get_db_connection()

    try:

        cursor.execute("""
            SELECT *
            FROM substations
            WHERE id=%s
        """, (substation_id,))

        substation = cursor.fetchone()
        if not substation:
            abort(404)
        cursor.execute("""
            SELECT *
            FROM travel_requests
            WHERE substation_id=%s
            ORDER BY id DESC
        """, (substation_id,))

        requests_data = cursor.fetchall()

        return render_template(
            'site_requests.html',
            substation=substation,
            requests_data=requests_data
        )

    finally:

        cursor.close()
        db.close()


# =========================================
# APPROVE REQUEST
# =========================================

@app.route('/approve-request/<int:request_id>')
def approve_request(request_id):

    if 'username' not in session:
        return redirect('/login')

    db, cursor = get_db_connection()

    try:

        # =========================================
        # ADMIN APPROVAL
        # =========================================

        if session['role'] == 'admin':

            cursor.execute("""
                UPDATE travel_requests
                SET
                    admin_approval='Approved',
                    status='Pending'
                WHERE id=%s
            """, (request_id,))

            db.commit()

        # =========================================
        # CEO APPROVAL
        # =========================================

        elif session['role'] == 'ceo':

            cursor.execute("""
                UPDATE travel_requests
                SET
                    ceo_approval='Approved',
                    status='Approved'
                WHERE id=%s
            """, (request_id,))

            db.commit()

            # =========================================
            # FETCH TRAVEL REQUEST
            # =========================================

            cursor.execute("""
                SELECT *
                FROM travel_requests
                WHERE id=%s
            """, (request_id,))

            travel = cursor.fetchone()

            # =========================================
            # FETCH EMPLOYEE EMAIL
            # =========================================

            cursor.execute("""
                SELECT *
                FROM users
                WHERE emp_id=%s
            """, (travel['emp_id'],))

            employee = cursor.fetchone()

            employee_email = employee['email']

            # =========================================
            # FETCH ADMIN EMAIL
            # =========================================

            cursor.execute("""
                SELECT *
                FROM users
                WHERE role='admin'
                LIMIT 1
            """)

            admin = cursor.fetchone()

            admin_email = admin['email']

            # =========================================
            # FETCH ACCOUNTS EMAIL
            # =========================================

            cursor.execute("""
                SELECT *
                FROM users
                WHERE role='accounts'
                LIMIT 1
            """)

            accounts = cursor.fetchone()

            accounts_email = None

            if accounts:

                accounts_email = accounts['email']

            # =========================================
            # CEO EMAIL
            # =========================================

            ceo_email = session['email']

            # =========================================
            # CREATE RECIPIENTS
            # =========================================

            recipients = [
                employee_email,
                admin_email,
                ceo_email
            ]

            if accounts_email:

                recipients.append(accounts_email)

            # =========================================
            # CREATE EMAIL
            # =========================================

            msg = Message(

                subject=f"Travel Request - {travel['emp_name']}",

                sender=app.config['MAIL_USERNAME'],

                recipients=recipients

            )

            msg.body = f"""
Travel Request Approved

Employee:
{travel['emp_name']}

Project:
{travel['project_name']}

Site:
{travel['site_name']}

Purpose:
{travel['purpose']}

Status:
Approved
"""

            # =========================================
            # ATTACH PDF
            # =========================================

            pdf_path = os.path.join(
                'pdfs',
                travel['pdf_file']
            )

            if os.path.exists(pdf_path):
                with open(pdf_path, 'rb') as pdf:
                    msg.attach(
                        filename=travel['pdf_file'],
                        content_type='application/pdf',
                        data=pdf.read()
                    )
            # =========================================
            # SEND EMAIL
            # =========================================

            try:

                mail.send(msg)

                logging.info("APPROVAL EMAIL SENT SUCCESSFULLY")

            except Exception as e:

                logging.error(f"APPROVAL EMAIL ERROR: {str(e)}")

        else:

            abort(403)

        return redirect('/history')

    finally:

        cursor.close()
        db.close()
# =========================================
# DECLINE REQUEST
# =========================================

@app.route('/decline-request/<int:request_id>')
def decline_request(request_id):

    if 'username' not in session:
        return redirect('/login')

    db, cursor = get_db_connection()

    try:

        # =========================================
        # ADMIN DECLINE
        # =========================================

        if session['role'] == 'admin':

            cursor.execute("""
                UPDATE travel_requests
                SET
                    admin_approval='Declined',
                    status='Declined'
                WHERE id=%s
            """, (request_id,))

        # =========================================
        # CEO DECLINE
        # =========================================

        elif session['role'] == 'ceo':

            cursor.execute("""
                UPDATE travel_requests
                SET
                    ceo_approval='Declined',
                    status='Declined'
                WHERE id=%s
            """, (request_id,))

        else:

            abort(403)

        db.commit()

        # =========================================
        # FETCH TRAVEL REQUEST
        # =========================================

        cursor.execute("""
            SELECT *
            FROM travel_requests
            WHERE id=%s
        """, (request_id,))

        travel = cursor.fetchone()

        # =========================================
        # FETCH EMPLOYEE EMAIL
        # =========================================

        cursor.execute("""
            SELECT *
            FROM users
            WHERE emp_id=%s
        """, (travel['emp_id'],))

        employee = cursor.fetchone()

        employee_email = employee['email']

        # =========================================
        # WHO DECLINED
        # =========================================

        declined_by = session['emp_name'].title()

        # =========================================
        # EMAIL
        # =========================================

        msg = Message(

            subject=f"Travel Request Declined - {travel['emp_name']}",

            sender=app.config['MAIL_USERNAME'],

            recipients=[employee_email]

        )

        msg.body = f"""
Your travel request has been DECLINED.

Declined By:
{declined_by}

Project:
{travel['project_name']}

Site:
{travel['site_name']}

Purpose:
{travel['purpose']}
"""

        # =========================================
        # ATTACH PDF
        # =========================================

        pdf_path = os.path.join(
            'pdfs',
            travel['pdf_file']
        )

        if os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as pdf:
                msg.attach(
                    filename=travel['pdf_file'],
                    content_type='application/pdf',
                    data=pdf.read()
                )
        # =========================================
        # SEND MAIL
        # =========================================

        try:

            mail.send(msg)

            logging.info("DECLINE EMAIL SENT SUCCESSFULLY")

        except Exception as e:

            logging.error(f"DECLINE EMAIL ERROR: {str(e)}")

        return redirect('/history')

    finally:

        cursor.close()
        db.close()
# =========================================
# QUERY REQUEST
# =========================================

@app.route('/query/<int:id>')
def query_request(id):

    if 'username' not in session:
        return redirect('/login')

    if session['role'] not in ['admin', 'ceo']:
        abort(403)

    db, cursor = get_db_connection()

    try:

        query_person = session['emp_name'].title()

        # =========================================
        # ADMIN QUERY
        # =========================================

        if session['role'] == 'admin':

            status_text = f"{query_person} Query"

            cursor.execute("""
                UPDATE travel_requests
                SET
                    status=%s,
                    admin_approval='Query'
                WHERE id=%s
            """, (
                status_text,
                id
            ))

        # =========================================
        # CEO QUERY
        # =========================================

        elif session['role'] == 'ceo':

            status_text = f"{query_person} Query"

            cursor.execute("""
                UPDATE travel_requests
                SET
                    status=%s,
                    ceo_approval='Query'
                WHERE id=%s
            """, (
                status_text,
                id
            ))

        db.commit()

        # =========================================
        # FETCH TRAVEL REQUEST
        # =========================================

        cursor.execute("""
            SELECT *
            FROM travel_requests
            WHERE id=%s
        """, (id,))

        travel = cursor.fetchone()

        # =========================================
        # FETCH EMPLOYEE EMAIL
        # =========================================

        cursor.execute("""
            SELECT *
            FROM users
            WHERE emp_id=%s
        """, (travel['emp_id'],))

        employee = cursor.fetchone()

        employee_email = employee['email']

        # =========================================
        # EMAIL MESSAGE
        # =========================================

        msg = Message(

            subject=f"Travel Request Query - {travel['emp_name']}",

            sender=app.config['MAIL_USERNAME'],

            recipients=[employee_email]

        )

        msg.body = f"""
Your travel request has been marked as QUERY.

Query Raised By:
{query_person}

Project:
{travel['project_name']}

Site:
{travel['site_name']}

Purpose:
{travel['purpose']}

Please contact the above person for clarification.
"""

        # =========================================
        # ATTACH PDF
        # =========================================

        pdf_path = os.path.join(
            'pdfs',
            travel['pdf_file']
        )

        if os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as pdf:
                msg.attach(
                    filename=travel['pdf_file'],
                    content_type='application/pdf',
                    data=pdf.read()
                )

        # =========================================
        # SEND EMAIL
        # =========================================

        try:

            mail.send(msg)

            logging.info("QUERY EMAIL SENT SUCCESSFULLY")

        except Exception as e:

            logging.error(f"QUERY EMAIL ERROR: {str(e)}")

        return redirect('/history')

    finally:

        cursor.close()
        db.close()
# =========================================
# RUN APP
# =========================================

if __name__ == '__main__':
    app.run(debug=False)