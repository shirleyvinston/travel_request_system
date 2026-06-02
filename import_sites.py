import pandas as pd
import mysql.connector

# Read Excel file
excel_file = "NCS REGION LIST.xlsx"

# Read Site Code sheet
df = pd.read_excel(
    excel_file,
    sheet_name="Site Code",
    header=3
)

# Keep only needed columns
df = df[['Site Code', 'Site Name']]

# Remove empty rows
df = df.dropna()

# Connect MySQL
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Shirley230106!",
    database="travel_db"
)

cursor = db.cursor()

# Insert data into MySQL
for index, row in df.iterrows():

    query = """
    INSERT INTO sites(site_code, site_name)
    VALUES (%s, %s)
    """

    values = (
        row['Site Code'],
        row['Site Name']
    )

    cursor.execute(query, values)

db.commit()

print("Sites imported successfully!")