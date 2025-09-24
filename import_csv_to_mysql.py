import os
import pandas as pd
import pymysql
import numpy as np

# Paramètres de connexion MySQL locale
host = 'localhost'
user = 'root'
password = ''  # Mets ton mot de passe si besoin
database = 'enterprise_db'

# Dossier contenant les CSV exportés
input_dir = 'csv_exports'

# Connexion à la base locale
conn = pymysql.connect(host=host, user=user, password=password, database=database)
cursor = conn.cursor()

for filename in os.listdir(input_dir):
    if filename.endswith('.csv'):
        table_name = filename[:-4]
        csv_path = os.path.join(input_dir, filename)
        print(f"Import de {csv_path} dans la table {table_name}...")

        df = pd.read_csv(csv_path)

        # Création de la table si elle n'existe pas (types VARCHAR génériques)
        columns = ', '.join([f"`{col}` VARCHAR(255)" for col in df.columns])
        create_table_sql = f"CREATE TABLE IF NOT EXISTS `{table_name}` ({columns});"
        cursor.execute(create_table_sql)

        # Suppression des données existantes (optionnel)
        # cursor.execute(f"TRUNCATE TABLE `{table_name}`;")
         # Remplace les chaînes vides et NaN par None (NULL SQL)
        df = df.replace({np.nan: None, '': None})
        # Insertion des données
        for _, row in df.iterrows():
            placeholders = ', '.join(['%s'] * len(row))
            insert_sql = f"INSERT INTO `{table_name}` ({', '.join([f'`{col}`' for col in df.columns])}) VALUES ({placeholders})"
            cursor.execute(insert_sql, tuple(row))
        conn.commit()
        print(f"Table {table_name} importée.")

cursor.close()
conn.close()
print("Import terminé.")