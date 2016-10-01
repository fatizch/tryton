/*
 * Remove obsolete translations modules from database.
 *
 * Apply with:
 * psql -f drop_some_translation_modules.sql -U username -d database -h host
 */
DELETE FROM ir_module WHERE name in ('account_payment_cog_translation', 'bank_cog_translation', 'company_cog_translation');
