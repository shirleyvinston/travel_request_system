import os
from dotenv import load_dotenv
from mysql.connector import pooling

load_dotenv()

db_pool = pooling.MySQLConnectionPool(

    pool_name="travel_pool",

    pool_size=5,

    host=os.getenv("DB_HOST"),

    user=os.getenv("DB_USER"),

    password=os.getenv("DB_PASSWORD"),

    database=os.getenv("DB_NAME")

)

def get_db_connection():

    db = db_pool.get_connection()

    cursor = db.cursor(dictionary=True)

    return db, cursor