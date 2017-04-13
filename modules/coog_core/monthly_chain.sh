#!/bin/bash
# This script checks if today is a weekday or a month first day eve.
# If yes, it executes the different chain.
# There is another test executing the monthly chain.
# You can add chain regarding the executing frequencies.
# This script is executed every day, thanks to a crontab.

TODAY_DATE="$(date --iso)"

TOMORROW_DATE="$(date --date=tomorrow +%d)"

MONDAY_DATE="$(date --d "+3 days" +%d)"

TODAY_WEEK_DAY="$(date +%u)"

LAST_DAY_OF_THE_MONTH="$(date -d "$(date +%Y-%m-01) +1 month -1 day" +%Y-%m-%d)"


if [ "$TODAY_WEEK_DAY" -lt "6" ] \
    && [ "$TODAY_WEEK_DAY" -gt "0" ] 
then

    coog chain -- account_payment_sepa_cog payment_fail \
        --treatment_date="$TODAY_DATE" \
        --in=/tmp --out=/tmp

    coog chain -- account_dunning_cog dunning --treatment_date="$TODAY_DATE"

    coog chain -- contract terminate_contract --treatment_date="$TODAY_DATE"

# Here starts the monthly chain.

    if [ "$TODAY_WEEK_DAY" == "5" ] \
        && [ "$MONDAY_DATE" -lt  "04" ] \
        || [ "$TOMORROW_DATE" == "01" ] 
    then

        coog chain -- commission_insurance commission \
            --treatment_date="$LAST_DAY_OF_THE_MONTH" \
            --agent_type=agent

         #the next chain crashes on the
         #commission.invoice_principal.create_empty, which is not normal having
         #regard to my understanding of the batch.
         #I need some help with this issue.

        coog chain -- commission_insurer commission \
            --treatment_date="$LAST_DAY_OF_THE_MONTH"

    fi

# Here ends the monthly chain.

    coog chain -- contract_insurance_invoice invoice \
        --treatment_date="$TODAY_DATE"

    coog chain -- account_payment_sepa_cog payment_working_days \
        --connexion_date="$TODAY_DATE" \
        --working_days=4 \
        --conf_code=jours_ouvres \
        --payment_kind=receivable \
        --journal_methods=sepa

    coog chain -- account_payment_sepa_cog payment \
        --treatment_date="$TODAY_DATE" \
        --payment_kind=payable \
        --journal_methods=sepa

fi
