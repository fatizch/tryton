DO $$
BEGIN
/* level 2 */
/* first argument is table name, second argument is a list of field to md5, third argument a list of fields to set null */
PERFORM anon_table('party_party', 'name, first_name, ssn, commercial_name, birth_name, sepa_creditor_identifier', 'siren');
PERFORM anon_table('party_contact_mechanism', 'value, value_compact', '');
PERFORM anon_table('party_address', 'street, name, zip, city', 'siret_nic');
PERFORM anon_table('party_identifier', 'code', '');
PERFORM anon_table('contract_option_beneficiary', 'reference', '');
PERFORM anon_table('contract_clause', 'text', '');
PERFORM anon_table('contract_option', 'customized_beneficiary_clause', '');
PERFORM anon_table('report_template', 'email_dest, email_bcc, email_cc', '');
PERFORM anon_table('res_user', 'name', '');
update res_user set login = md5(login) where login != 'admin';
PERFORM anon_table('ir_attachment', 'name', 'data');
PERFORM anon_table('account_invoice', '', 'comment, description');
PERFORM anon_table('account_invoice_line', 'description', '');
PERFORM anon_table('account_statement_line', '', 'description');
PERFORM anon_table('account_payment', '', 'description');
END $$;
