import mysql.connector

conn = mysql.connector.connect(host="localhost", user="root", password="")
cursor = conn.cursor()
cursor.execute("CREATE DATABASE IF NOT EXISTS mydb")
cursor.execute("USE mydb")

with open('data/sql/init.sql', 'r', encoding='utf-8') as f:
    sql = f.read()

for result in cursor.execute(sql, multi=True):
    pass

conn.commit()
print("SQL initialization complete!")
