import mysql.connector

conn = mysql.connector.connect(host="localhost", user="root", password="")
cursor = conn.cursor()
cursor.execute("DROP DATABASE IF EXISTS mydb")
cursor.execute("CREATE DATABASE mydb")
cursor.execute("USE mydb")

with open('data/sql/init.sql', 'r', encoding='utf-8') as f:
    sql = f.read()

for statement in sql.split(';'):
    if statement.strip():
        try:
            cursor.execute(statement)
        except Exception as e:
            pass

conn.commit()
print("SQL initialization complete!")
