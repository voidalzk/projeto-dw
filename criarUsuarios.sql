-- Conectar-se ao SQL Server usando o SQL Server Management Studio (SSMS)

-- Criar um novo login
CREATE LOGIN user_novo WITH PASSWORD = '123';

-- Criar um usuário no banco de dados ADS
USE ADS;
CREATE USER user_novo FOR LOGIN user_novo;

-- Conceder permissões ao usuário
ALTER ROLE db_owner ADD MEMBER novo_usuario;