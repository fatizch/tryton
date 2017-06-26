- **Batch for rejecting inactive quotes:**
    Add a batch to decline contracts which corresponde to the following conditions:
    - quote status
    - The last modification date of a quote exceeds the maximum date defined in the "Product administration" configuration.
    Consequently, the status of these contract are passed to "Declined"
    The sub-status is assigned depending on the field "Automatic decline reason" in the "Product administration" configuration.
