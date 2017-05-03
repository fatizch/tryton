- **Recompule a contracts set premiums when changing one of the contracts**

- **Handle fees by a contracts set**

- **Schedule payments for a contracts set** This feature allows to provide
  a contracts set aggregated invoices information to a report template. Inside
  a contracts set (contract.set), contracts are grouped by payment mode,
  receivable payment's bank account number, and end date.
  Inside a contracts set, all invoices which have the same planned payment date
  for a receivable payment, or the same scheduled start date for a cheque
  payment, are summed together. In a report templace, it is then possible to
  display the invoices amounts aggregated by contracts sets. This is done by
  iterating on the contract_groups_info function:

      <for each="contract_set in objects">
      <for each="group in contract_set.contract_groups_info()">
      <for each="invoice in group['invoices']">
      <invoice.planned_payment_date>
      <invoice.total_amount>
      </for>
      </for>
      </for>
