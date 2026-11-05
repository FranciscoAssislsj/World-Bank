-- 011_dashboard_leitor.sql
-- Usuário dos dashboards: só lê a gold (D-079). A regra "dashboard lê só gold" passa
-- a ser garantida pelo banco. A senha não fica aqui: o migrate a define a partir do
-- DASHBOARD_DATABASE_URL. Sem esse valor, o usuário existe, mas não consegue entrar.

do $$
begin
    if not exists (select from pg_roles where rolname = 'dashboard_leitor') then
        create role dashboard_leitor nologin;
    end if;
end
$$;

grant usage on schema gold to dashboard_leitor;
grant select on all tables in schema gold to dashboard_leitor;

-- O build-gold apaga e recria as views, e isso apaga as permissões delas. Este padrão
-- vale para toda view que o usuário do pipeline criar depois nesse schema.
alter default privileges in schema gold grant select on tables to dashboard_leitor;

-- Defesa extra: toda transação é só de leitura, e uma consulta presa não trava o banco.
alter role dashboard_leitor set default_transaction_read_only = on;
alter role dashboard_leitor set statement_timeout = '30s';
