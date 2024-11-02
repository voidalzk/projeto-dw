import pyodbc
import pymysql

# Conexão com o SQL Server
sql_server_conn = pyodbc.connect(
    'DRIVER={ODBC Driver 18 for SQL Server};'
    'SERVER=localhost;'
    'DATABASE=ADS;'
    'Trusted_Connection=yes;'
)

# Conexão com o MySQL
mysql_conn = pymysql.connect(
    host='localhost',
    user='root@localhost',
    password='123',
    database='ADS'
)

# Função para extrair dados do SQL Server
def extract_data(query):
    cursor = sql_server_conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    return rows

# Função para transformar os dados
def transform_data(rows):
    transformed_rows = []
    for row in rows:
        transformed_row = [str(item).strip() for item in row]  # Exemplo de transformação
        transformed_rows.append(transformed_row)
    return transformed_rows

# Função para carregar dados no MySQL
def load_data(table, rows):
    cursor = mysql_conn.cursor()
    for row in rows:
        placeholders = ', '.join(['%s'] * len(row))
        sql = f"INSERT INTO {table} VALUES ({placeholders})"
        cursor.execute(sql, row)
    mysql_conn.commit()
    cursor.close()

# Executar ETL
query = "SELECT * FROM tb001_uf"
rows = extract_data(query)
transformed_rows = transform_data(rows)
load_data('tb001_uf', transformed_rows)

# Fechar conexões
sql_server_conn.close()
mysql_conn.close()