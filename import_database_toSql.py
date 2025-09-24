import os
import pandas as pd

input_dir = 'csv_exports'
output_sql = 'import_all_tables.sql'

def guess_sql_type(series):
    if pd.api.types.is_integer_dtype(series):
        return 'INT'
    elif pd.api.types.is_float_dtype(series):
        return 'FLOAT'
    elif pd.api.types.is_bool_dtype(series):
        return 'TINYINT(1)'
    elif pd.api.types.is_datetime64_any_dtype(series):
        return 'DATETIME'
    elif series.dropna().apply(lambda x: str(x).lower() in ['true', 'false']).all():
        return 'TINYINT(1)'
    elif series.dropna().apply(lambda x: len(str(x))).max() <= 20 and series.dropna().apply(lambda x: str(x).isdigit()).all():
        return 'VARCHAR(20)'
    else:
        max_len = series.dropna().apply(lambda x: len(str(x))).max()
        if max_len <= 50:
            return 'VARCHAR(50)'
        elif max_len <= 255:
            return 'VARCHAR(255)'
        else:
            return 'TEXT'

def escape_sql_value(val):
    if pd.isna(val) or val == '':
        return "NULL"
    # Remplace les apostrophes par deux apostrophes pour SQL
    return "'" + str(val).replace("'", "''") + "'"

with open(output_sql, 'w', encoding='utf-8') as sqlfile:
    for filename in os.listdir(input_dir):
        if filename.endswith('.csv'):
            table_name = filename[:-4]
            csv_path = os.path.join(input_dir, filename)
            df = pd.read_csv(csv_path)
            # Détecte le type de chaque colonne
            columns = ', '.join([
                f'`{col}` {guess_sql_type(df[col])}'
                for col in df.columns
            ])
            sqlfile.write(f'DROP TABLE IF EXISTS `{table_name}`;\n')
            sqlfile.write(f'CREATE TABLE `{table_name}` ({columns});\n')
            # Génère les INSERT
            for _, row in df.iterrows():
                values = ', '.join([escape_sql_value(val) for val in row])
                sqlfile.write(f"INSERT INTO `{table_name}` ({', '.join([f'`{col}`' for col in df.columns])}) VALUES ({values});\n")
            sqlfile.write('\n')

print(f"Fichier SQL généré : {output_sql}")