/* level 0 */
DO $$
BEGIN
/* first argument is table name, second argument is a list of field to md5, third argument a list of fields to set null */
PERFORM anon_table('contract', 'contract_number, quote_number', '');
PERFORM anon_table('party_party', 'code', '');
END $$;
