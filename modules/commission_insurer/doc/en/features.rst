- **Insurer invoices creation**: Through a dedicated entry point, insurer
  invoices are generated with the following behavior : Every line in the
  insurer's waiting account is added to the invoice, and every insurer
  commission on those lines are deducted. The final amount on the invoice will
  be the remaining amount

- **Insurer waiting account**: Insurer have a waiting account field which is
  used to create and identify the insurer invoices lines. This account is
  usually fed by client invoices moves

- **Insurer invoices batches**: Generating the insurer invoices may be time
  consuming, especially for large insurers which may be related to thousands of
  contracts. So batches are available to perform this in a performance
  optimized way
