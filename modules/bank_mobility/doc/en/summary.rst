The banking mobility norm defines a new sepa file (named Flow 5) that provides all information to update billing informations.

From the flow 5 file, Coog extracts:
- the file Id and the Mobility modification Id,
- the modification signature date,
- original IBAN and BIC,
- updated IBAN and BIC,
- sepa mandate identifications related to the modification

The original bank account is updated to set its end date.
The updated bank account is created or updated. Its owners are the mandate payers if mandate identification are provided, original bank account owners if not.
Sepa Mandates are amended with the new bank account.
Any contract using one of the sepa mandates after the signature date will be endorsed using the dedicated bank account modification endorsement.