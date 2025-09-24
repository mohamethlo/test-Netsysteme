import os
import pymysql
import pandas as pd

# Paramètres de connexion MySQL (remplace par tes infos)
""" host = 'staffnetsys.mysql.pythonanywhere-services.com'
user = 'staffnetsys'
password = 'netsys995'
database = 'staffnetsys$monitoring_db'
 """
host = 'localhost'
user = 'root'
password = ''  # Mets ton mot de passe si besoin
database = 'enterprise_db'
# Dossier de sortie pour les CSV
output_dir = 'csv_exports'
os.makedirs(output_dir, exist_ok=True)

# Connexion à la base
conn = pymysql.connect(host=host, user=user, password=password, database=database)

try:
    with conn.cursor() as cursor:
        # Récupérer la liste des tables
        cursor.execute("SHOW TABLES;")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Tables trouvées : {tables}")

        for table in tables:
            print(f"Export de la table : {table}")
            df = pd.read_sql(f"SELECT * FROM `{table}`", conn)
            csv_path = os.path.join(output_dir, f"{table}.csv")
            df.to_csv(csv_path, index=False, encoding='utf-8')
            print(f"Table {table} exportée vers {csv_path}")

finally:
    conn.close()

print("Export terminé.")