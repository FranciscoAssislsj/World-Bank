-- 001_schemas.sql
-- Cria os schemas da arquitetura medalhão e o schema de controle.
--   bronze: respostas da API exatamente como vieram (append-only)
--   silver: dados limpos, tipados e modelados em esquema estrela
--   gold:   indicadores prontos para os dashboards (views de sql/gold/)
--   etl:    controle do pipeline (migrações aplicadas, execuções)

create schema if not exists bronze;
create schema if not exists silver;
create schema if not exists gold;
create schema if not exists etl;
