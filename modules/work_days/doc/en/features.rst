- **Holidays configuration :** Allows to manually configure holidays of three
    types:

    - Weekly days off: generally weekends
    - Easter holidays: holidays whose dates depend on easter date
    - Fixed holidays: annual holidays month/day

- **Work day computation :** for each configuration containing a certain number
    of holidays, it allows computing a specific work day by skipping all
    holidays given a start date and a certain number of open days. 

- **Batch parameters configuration**: Uses the 'work_days.configuration' class
    to compute the parameter 'treatment_date' for batches which require it.
    Computation is done using the following batch parameters:

    - connection_date: start date. By default, it is equal to the current
        date.
    - working_days: open days' number.
    - conf_code: holidays configuration to be used.

    Warning: if the treatment_date parameter is specified for this batch, its
    value will be taken into account and no computation will be made even if the
    above parameters are specified.
