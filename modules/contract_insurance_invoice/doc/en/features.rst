- **Payment suspensions :** It is now possible to suspend the payments for a
  given contract billing information. These suspensions could be automatics 
  (Actually defined in a journal failure action) or manuals via a button in the 
  contract billing informations list page. The un-suspension can also be
  automatic (suspension is inactive when the associated account move line
  is reconciled) or manual (The same way as the manual suspension).
  A relate is added on billing informations to easely find associated suspensions.
  Finally, a new page showing all contracts with a suspended billing information
  has been added to the contract list view.

- **Configuration of invoice settings :** It is possible to define using
  configuration a set of invoice rules, as well as products and / or conditions
  under which these rules are available. These rules contain typically the payment
  method used and the frequency of invoicing.

- **Manage configuration of invoicing :** The contracts requiring invoice
  configuration to be filled, so that the system is capable of deciding when
  and how to generate invoices. These configurations are limited to those
  available for the selected product on a contract.

- **Connecting Accounts :** From the time invoices are generated, it is necessary
  to account for them. The pure configuration data 
  (products, offered guarentees, fees...) now require to fill the accounts
  to be used during an invoice operation.

- **Insurance receipts :** The insurance receipts invluce extra
  information in relation to *standard* invoices.
  In particuliar, they are attached to a covered period on a contract, who
  has generated them. Furthermore, we introduce the seperation of fees.

- **Invoice details :** In order to precisely understand the origin of each
  generated invoice line, following a billing of a contract, each generated
  invoice line has a *details* who links the line to the business data that
  generated the invoice. This equally allows the simplification of 
  extractions based on premiums.

- **Modified bank account :** Allow the modification of a bank account
  to be used for the invoicing on a contract, and to propagate to contract
  who use the same account.

- **Tarification API :** It is possible to obtain via a RPC call
  the rates for a potential contract. Nothing is saved in the database.

- **Included taxes :** It is possible to define in the configuration that the
  premium is defined taxes included or taxes excluded. This option is not
  available from a product only if the rounding method defined in the configuration
  is rounded by line.

- **Accounting by contract :** The account movement lines attached to a
  contract are linked to this contract. This link is propagated by the 
  reconciliation (the lines reconcile the lines attached to a contract are
  reattached to this contract), only under the condition that there is no
  ambiguity on a concered contract.

- **More flexible reconciliation :** It is now possible during reconciliation
  operations to transfer the eventual remains to an parties account, or even
  attach to a contract.

- **Exhaustion of overpayment by invoicing:** A batch is available to allow
  the exhaustion of overpayment for a contract by lettering with invoices
  generated in the future.
