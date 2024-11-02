import pyodbc
import pymysql
from datetime import datetime, timedelta

# Função para determinar o tipo com base na categoria
def definir_tipo(categoria):
    if categoria in [1, 2]:
        return 1
    elif categoria in [3, 4, 5]:
        return 2
    elif categoria in [6, 7, 8]:
        return 3
    else:
        return None  # ou outro valor padrão

def transfer_data(sql_cursor, mysql_cursor, select_query, insert_query, process_row=None):
    sql_cursor.execute(select_query)
    rows_sql = sql_cursor.fetchall()

    for row in rows_sql:
        if process_row:
            row = process_row(row)
        mysql_cursor.execute(insert_query, row)

# Conexão com SQL Server
sql_conn = pyodbc.connect(
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=localhost;'
    'DATABASE=ADS;'
    'Trusted_Connection=yes;'
)
cursor_sql = sql_conn.cursor()

# Conexão com MySQL
mysql_conn = pymysql.connect(
    host='localhost',
    user='root',
    password='123',
    database='projeto_dw'
)
cursor_mysql = mysql_conn.cursor()

# ETL para tb007_tempo (Dimensão Tempo) - Gerando datas
insert_tempo = """
INSERT INTO tb007_tempo (tb007_tempo_cod, tb007_tempo_data, tb007_tempo_dia, tb007_tempo_mes, tb007_tempo_ano)
VALUES (%s, %s, %s, %s, %s)
"""

start_date = datetime(2023, 1, 1)
end_date = datetime(2024, 12, 31)
delta = timedelta(days=1)

current_date = start_date
while current_date <= end_date:
    tempo_cod = int(current_date.strftime('%Y%m%d'))
    data = current_date.date()
    dia = current_date.day
    mes = current_date.month
    ano = current_date.year
    cursor_mysql.execute(insert_tempo, (tempo_cod, data, dia, mes, ano))
    current_date += delta

# ETL para tb013_categorias -> tb001_categorias
select_categorias = "SELECT tb013_cod_categoria, tb013_descricao FROM ADS.dbo.tb013_categorias"
insert_categorias = """
INSERT INTO tb001_categorias (tb001_cod_categoria, tb001_descricao)
VALUES (%s, %s)
"""
transfer_data(cursor_sql, cursor_mysql, select_categorias, insert_categorias)

# Extração e Transformação dos Dados
cursor_sql_server = sql_conn.cursor()
cursor_sql_server.execute(
    "SELECT tb012_cod_produto, tb013_cod_categoria, tb012_descricao FROM tb012_produtos")

# Preparar inserção no MySQL
for tb012_cod_produto, tb013_cod_categoria, tb012_descricao in cursor_sql_server:
    tb003_cod_tipo = definir_tipo(tb013_cod_categoria)

    # Verifica se o tipo é válido
    if tb003_cod_tipo is not None:
        cursor_mysql.execute(
            """
            INSERT INTO tb003_produtos (tb003_cod_produto, tb003_cod_categoria, tb003_descricao, tb003_cod_tipo) 
            VALUES (%s, %s, %s, %s)
            """,
            (tb012_cod_produto, tb013_cod_categoria, tb012_descricao, tb003_cod_tipo)
        )

# ETL para tb004_lojas -> tb004_filial
select_filial = """
SELECT 
    l.tb004_cod_loja,
    l.tb004_inscricao_estadual,
    CONCAT(u.tb001_nome_estado, ', ', c.tb002_nome_cidade, ', ', e.tb003_bairro, ', ', e.tb003_nome_rua, ' ', IFNULL(e.tb003_complemento, '')) AS endereco_completo,
    l.tb004_cnpj_loja
FROM 
    ADS.dbo.tb004_lojas l
JOIN 
    ADS.dbo.tb003_enderecos e ON l.tb003_cod_endereco = e.tb003_cod_endereco
JOIN 
    ADS.dbo.tb002_cidades c ON e.tb002_cod_cidade = c.tb002_cod_cidade AND e.tb001_sigla_uf = c.tb001_sigla_uf
JOIN 
    ADS.dbo.tb001_uf u ON e.tb001_sigla_uf = u.tb001_sigla_uf
"""
insert_filial = """
INSERT INTO tb004_filial (tb004_cod_filial, tb004_inscricao_estadual, tb004_endereco, tb004_cnpj_filial)
VALUES (%s, %s, %s, %s)
"""

def process_filial_row(row):
    cod_filial = row[0]
    inscricao_estadual = row[1]
    endereco_completo = row[2]
    cnpj_filial = row[3]
    return (cod_filial, inscricao_estadual, endereco_completo, cnpj_filial)

transfer_data(cursor_sql, cursor_mysql, select_filial, insert_filial, process_filial_row)

# ETL para clientes
select_clientes = """
SELECT tb010_cpf, tb010_nome
FROM ADS.dbo.tb010_clientes

UNION ALL

SELECT ca.tb010_cpf, ca.tb010_nome
FROM ADS.dbo.tb010_clientes_antigos ca
WHERE NOT EXISTS (
    SELECT 1
    FROM ADS.dbo.tb010_clientes c
    WHERE c.tb010_cpf = ca.tb010_cpf
)
"""
insert_clientes = """
INSERT INTO tb009_cliente (tb009_cpf, tb009_nome_cliente)
VALUES (%s, %s)
"""
transfer_data(cursor_sql, cursor_mysql, select_clientes, insert_clientes)

select_funcionarios = """
SELECT 
    f.tb005_matricula, 
    f.tb005_nome_completo, 
    f.tb005_CPF
FROM ADS.dbo.tb005_funcionarios f
"""
insert_funcionarios = """
INSERT INTO tb010_funcionario (tb010_cod_funcionario, tb010_nome_funcionario, tb010_cpf)
VALUES (%s, %s, %s)
"""

def process_funcionario_row(row):
    cod_funcionario = row[0]
    nome_funcionario = row[1]
    cpf = row[2]
    return (cod_funcionario, nome_funcionario, cpf)

transfer_data(cursor_sql, cursor_mysql, select_funcionarios, insert_funcionarios, process_funcionario_row)

#inserindo na fato vendas
select_vendas = """
SELECT
    v.tb010_012_quantidade,
    v.tb010_012_valor_unitario,
    v.tb012_cod_produto,
    f.tb004_cod_loja,
    v.tb010_012_data,
    v.tb010_cpf,
    v.tb005_matricula
FROM ADS.dbo.tb010_012_vendas v
JOIN ADS.dbo.tb005_funcionarios f ON v.tb005_matricula = f.tb005_matricula
"""

insert_vendas = """
INSERT INTO tb011_vendas (
    tb011_quantidade,
    tb011_valor,
    tb011_cod_produto,
    tb011_cod_filial,
    tb011_cod_tempo,
    tb011_cod_cliente,
    tb011_cod_funcionario
)
VALUES (%s, %s, %s, %s, %s, %s, %s)
"""

def process_venda_row(row):
    quantidade = row[0]
    valor = row[1]
    cod_produto = row[2]
    cod_filial = row[3]
    data_venda = row[4]
    cpf_cliente = row[5]
    cod_funcionario = row[6]

    if isinstance(data_venda, datetime):
        data_venda = data_venda.date()
    tempo_cod_venda = int(data_venda.strftime('%Y%m%d'))  # Formato YYYYMMDD

    return (quantidade, valor, cod_produto, cod_filial, tempo_cod_venda, cpf_cliente, cod_funcionario)

transfer_data(cursor_sql, cursor_mysql, select_vendas, insert_vendas, process_venda_row)

# ETL para tb011_vendas -> 1. Valor das vendas agrupada por produto, tipo e categoria.
select_vendas_agrupadas = """
SELECT
    p.tb003_cod_tipo AS tipo_id, 
    p.tb003_cod_categoria AS categoria_id,
    SUM(v.tb011_quantidade) AS total_quantidade,
    SUM(v.tb011_valor) AS total_valor
FROM tb011_vendas v
JOIN tb003_produtos p ON v.tb011_cod_produto = p.tb003_cod_produto
GROUP BY p.tb003_cod_tipo, p.tb003_cod_categoria
"""

insert_vendas_agrupadas = """
INSERT INTO tb011_vendas (
    tb011_quantidade,
    tb011_valor,
    tb011_cod_produto,
    tb011_cod_filial,
    tb011_cod_tempo,
    tb011_cod_cliente,
    tb011_cod_funcionario
)
VALUES (%s, %s, NULL, NULL, NULL, NULL, NULL)  
"""

def process_vendas_agrupadas(row):
    total_quantidade = row[2]
    total_valor = row[3]

    return (total_quantidade, total_valor) 

transfer_data(cursor_mysql, cursor_mysql, select_vendas_agrupadas, insert_vendas_agrupadas, process_vendas_agrupadas)

#ETL para tb011_vendas -> 2. Clientes que mais compraram na loja virtual com valor acumulado por período.
select_clientes_mais_compraram = """
SELECT
    v.tb011_cod_cliente,  -- Ajustar para a coluna correta
    SUM(v.tb011_valor) AS total_valor
FROM tb011_vendas v
GROUP BY v.tb011_cod_cliente
ORDER BY total_valor DESC
"""

insert_clientes_mais_compraram = """
INSERT INTO tb011_vendas (
    tb011_quantidade,
    tb011_valor,
    tb011_cod_produto,
    tb011_cod_filial,
    tb011_cod_tempo,
    tb011_cod_cliente,
    tb011_cod_funcionario
)
VALUES (0, %s, NULL, NULL, NULL, %s, NULL)  -- Altere NULL para 0 para tb011_quantidade
"""

def process_clientes_mais_compraram(row):
    total_valor = row[1]
    cpf_cliente = row[0]

    return (total_valor, cpf_cliente)

transfer_data(cursor_mysql, cursor_mysql, select_clientes_mais_compraram, insert_clientes_mais_compraram, process_clientes_mais_compraram)

# ETL para tb011_vendas -> 3. Volume das vendas por funcionário e localidade.
select_volume_vendas_funcionario = """
SELECT
    f.tb010_cod_funcionario,
    v.tb011_cod_filial, 
    SUM(v.tb011_quantidade) AS total_quantidade,
    SUM(v.tb011_valor) AS total_valor
FROM tb011_vendas v
JOIN tb010_funcionario f ON v.tb011_cod_funcionario = f.tb010_cod_funcionario
GROUP BY f.tb010_cod_funcionario, v.tb011_cod_filial
"""

insert_volume_vendas_funcionario = """
INSERT INTO tb011_vendas (
    tb011_quantidade,
    tb011_valor,
    tb011_cod_produto,
    tb011_cod_filial,
    tb011_cod_tempo,
    tb011_cod_cliente,
    tb011_cod_funcionario
)
VALUES (%s, %s, NULL, NULL, NULL, NULL, %s)
"""

def process_volume_vendas_funcionario(row):
    total_quantidade = row[2]
    total_valor = row[3]
    cod_funcionario = row[0]

    return (total_quantidade, total_valor, cod_funcionario)

transfer_data(cursor_mysql, cursor_mysql, select_volume_vendas_funcionario, insert_volume_vendas_funcionario, process_volume_vendas_funcionario)

# ETL para tb011_vendas -> 4. Quantidade de atendimentos realizados por localidade permitindo uma visão hierárquica ao longo do tempo.
select_atendimentos_por_localidade = """
SELECT
    v.tb011_cod_filial,
    v.tb011_cod_tempo,
    COUNT(*) AS quantidade_atendimentos
FROM tb011_vendas v
GROUP BY v.tb011_cod_filial, v.tb011_cod_tempo
"""

insert_atendimentos_por_localidade = """
INSERT INTO tb011_vendas (
    tb011_quantidade,
    tb011_valor,
    tb011_cod_produto,
    tb011_cod_filial,
    tb011_cod_tempo,
    tb011_cod_cliente,
    tb011_cod_funcionario
)
VALUES (%s, 0, NULL, %s, %s, NULL, NULL)  -- Altere NULL para 0 para tb011_valor
"""

def process_atendimentos_por_localidade(row):
    quantidade_atendimentos = row[2]
    cod_filial = row[0]
    tempo_id = row[1]

    return (quantidade_atendimentos, cod_filial, tempo_id)

transfer_data(cursor_mysql, cursor_mysql, select_atendimentos_por_localidade, insert_atendimentos_por_localidade, process_atendimentos_por_localidade)

# ETL para tb011_vendas -> 5. Valor das últimas compras realizadas por cliente e tempo decorrido até a data atual.
select_ultimas_compras = """
SELECT
    v.tb011_cod_cliente,
    MAX(v.tb011_cod_tempo) AS ultima_compra,
    SUM(v.tb011_valor) AS valor_total
FROM tb011_vendas v
GROUP BY v.tb011_cod_cliente
"""

insert_ultimas_compras = """
INSERT INTO tb011_vendas (
    tb011_quantidade,
    tb011_valor,
    tb011_cod_produto,
    tb011_cod_filial,
    tb011_cod_tempo,
    tb011_cod_cliente,
    tb011_cod_funcionario
)
VALUES (0, %s, NULL, NULL, NULL, %s, NULL)  -- Altere NULL para 0 para tb011_quantidade
"""

def process_ultimas_compras(row):
    valor_total = row[2]
    cpf_cliente = row[0]

    return (valor_total, cpf_cliente)

transfer_data(cursor_mysql, cursor_mysql, select_ultimas_compras, insert_ultimas_compras, process_ultimas_compras)

# Confirma as inserções e fecha conexões
mysql_conn.commit()
cursor_sql.close()
sql_conn.close()
cursor_mysql.close()
mysql_conn.close()
