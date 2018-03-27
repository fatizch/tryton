CREATE OR REPLACE FUNCTION col_exist(table_name text, col text) RETURNS integer as $$
DECLARE
    test text;
BEGIN
    if col is null then
        RETURN 0;
    end if;
    EXECUTE 'select ' || col || ' from ' || table_name || ' limit 1' INTO test;
    RETURN 1;
EXCEPTION
    WHEN undefined_column THEN
        RAISE NOTICE 'the column % does not exist, ignoring' , col;
        RETURN 0;
END
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION table_exist(table_name text) RETURNS integer as $$
DECLARE
    test text;
BEGIN
    if table_name is null then
        RETURN 0;
    end if;
    EXECUTE 'select * from ' || table_name || ' limit 1 ' INTO test;
    RETURN 1;
EXCEPTION
    WHEN undefined_table THEN
        RAISE NOTICE 'the table % does not exist, ignoring' , table_name;
        RETURN 0;
END
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION anon_table(table_name text, cols text, nulcolls text) RETURNS integer as $$
DECLARE
    cols_list text[];
    null_cols_list text[];
    i int;
    j int;
    col_test integer;
    table_test integer;
    history_table text := table_name || '__history';
    history_exist integer;
BEGIN
    table_test := table_exist(table_name);
    history_exist := table_exist(history_table);
    if table_test < 1 then
        RETURN 0;
    end if;
    select string_to_array(cols, ',') into cols_list;
    select string_to_array(nulcolls, ',') into null_cols_list;
    i := 1;
    loop 
        if cols_list = '{}' then
            EXIT;
        end if;
        if i > array_upper(cols_list, 1) then
            EXIT;
        else
            col_test := col_exist(table_name, cols_list[i]);
            if col_test > 0 then
                EXECUTE 'update ' || table_name  || ' set ' || cols_list[i]   || ' =md5(' || cols_list[i] || ');';
                if history_exist > 0 then
                    EXECUTE 'update ' || history_table  || ' set ' || cols_list[i]   || ' =md5(' || cols_list[i] || ');';
                end if;
            end if;
            i := i + 1;
        end if;
    end loop;
    j := 1;
    loop 
        if null_cols_list = '{}' then
            EXIT;
        end if;
        if j > array_upper(null_cols_list, 1) then
            EXIT;
        else
            col_test := col_exist(table_name, null_cols_list[i]);
            if col_test > 0 then
                EXECUTE 'update ' || table_name  || ' set ' || null_cols_list[i]   || ' = null;';
                if history_exist > 0 then
                    EXECUTE 'update ' || history_table || ' set ' || null_cols_list[i]   || ' = null;';
                end if;
            end if;
            j := j + 1;
        end if;
    end loop;
    RAISE NOTICE  'anonymized table % ', table_name;
    RETURN 0;
END
$$ LANGUAGE plpgsql;
