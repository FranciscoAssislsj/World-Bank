-- 013_silver_so_tratamento.sql
-- A silver passa a ser só a camada de tratamento: tabelas com nome de assunto, sem os
-- prefixos do modelo estrela. As dimensões e o fato agora ficam na gold (D-087).
-- Só muda o nome: os dados, as chaves e as ligações continuam iguais.

alter table silver.dim_regiao rename to regiao;
alter table silver.dim_nivel_renda rename to nivel_renda;
alter table silver.dim_tipo_emprestimo rename to tipo_emprestimo;
alter table silver.dim_fonte rename to fonte;
alter table silver.dim_topico rename to topico;
alter table silver.dim_pais rename to pais;
alter table silver.dim_indicador rename to indicador;
alter table silver.ponte_indicador_topico rename to indicador_topico;
alter table silver.fato_observacao rename to observacao;

-- As restrições levam o nome antigo da tabela; o índice da chave acompanha a restrição.
do $$
declare
    restricao record;
begin
    for restricao in
        select conrelid::regclass as tabela, conname as nome
        from pg_constraint
        where connamespace = 'silver'::regnamespace
          and conname ~ '^(dim_|fato_|ponte_)'
    loop
        execute format(
            'alter table %s rename constraint %I to %I',
            restricao.tabela,
            restricao.nome,
            replace(
                regexp_replace(
                    regexp_replace(restricao.nome, '^dim_', ''),
                    '^fato_observacao', 'observacao'
                ),
                'ponte_indicador_topico', 'indicador_topico'
            )
        );
    end loop;
end
$$;

alter index silver.fato_observacao_indicador_ano_idx
    rename to observacao_indicador_ano_idx;

comment on table silver.observacao is
    'Uma linha = o valor de um indicador para um país ou agregado em um ano. Filtre pais.e_agregado para não somar os dois (D-040).';
comment on column silver.valor_atipico.valor is 'O valor como está em silver.observacao.';
