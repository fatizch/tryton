#!/bin/bash
# This script checks if today is a weekday or a month first day eve.
# If yes, it executes the different chain.
# There is another test executing the monthly chain.
# You can add chain regarding the executing frequencies.
# This script is executed every day, thanks to a crontab.

if [[ "$#" -ne 3 ]]; then
    echo 'Usage: daily_chains WORKING_DAYS WORKING_DAYS_CONF SNAPSHOT_OUTPUT' 2>&1
    exit 1
fi

WORKING_DAYS="$1"
WORKING_DAYS_CONF="$2"
SNAPSHOT_OUTPUT="$3"


TODAY_DATE="$(date --iso)"
TOMORROW_DATE="$(date --date=tomorrow +%d)"
MONDAY_DATE="$(date -d "+3 days" +%d)"
TODAY_WEEK_DAY="$(date +%u)"
LAST_DAY_OF_THE_MONTH="$(date -d "$(date +%Y-%m-01) +1 month -1 day" +%Y-%m-%d)"


is_weekday() {  # return 0 if date is a work day
    [ "$TODAY_WEEK_DAY" -lt "6" ] && [ "$TODAY_WEEK_DAY" -gt "0" ]
}


check_modules() {
    coog module status "$1" | grep -q 'not activated'
    if [ "$?" -eq 0 ]; then
        echo "Missing module $1 Skipping chain..."
        return 1
    fi
    return 0
}


if is_weekday; then

    check_modules "account_payment_sepa_cog" &&             \
        coog chain -- account_payment_sepa_cog payment_fail \
            --treatment_date="$TODAY_DATE"

    check_modules "account_dunning_cog" &&                  \
        coog chain -- account_dunning_cog dunning           \
            --treatment_date="$TODAY_DATE"

    check_modules "contract" &&                             \
        coog chain -- contract decline_inactive             \
            --working_days="$WORKING_DAYS"                  \
            --conf_code="$WORKING_DAYS_CONF"

    check_modules "contract_term_renewal" &&                \
        coog chain -- contract_term_renewal renew           \
            --working_days="$WORKING_DAYS"                  \
            --conf_code="$WORKING_DAYS_CONF"

    check_modules "contract" &&                             \
        coog chain -- contract terminate_contract           \
            --treatment_date="$TODAY_DATE"

    check_modules "underwriting" &&                         \
        coog chain -- underwriting underwriting             \
            --treatment_date="$TODAY_DATE"

    # Executed for each new month
    if [ "$TODAY_WEEK_DAY" == "5" ] && [ "$MONDAY_DATE" -lt  "04" ] \
        || [ "$TOMORROW_DATE" == "01" ]; then

        check_modules "commission_insurance" &&             \
            coog chain -- commission_insurance commission   \
                --treatment_date="$LAST_DAY_OF_THE_MONTH"   \
                --with_draft=0                              \
                --agent_type=agent

        check_modules "commission_insurer" &&               \
            coog chain -- commission_insurer commission     \
            --treatment_date="$LAST_DAY_OF_THE_MONTH"
    fi

    check_modules "contract_insurance_invoice" &&           \
        coog chain -- contract_insurance_invoice invoice    \
            --working_days="$WORKING_DAYS"                  \
            --conf_code="$WORKING_DAYS_CONF"

    check_modules "account_payment_sepa_cog" &&             \
        coog chain -- account_payment_sepa_cog payment_working_days \
            --connexion_date="$TODAY_DATE"                  \
            --working_days="$WORKING_DAYS"                  \
            --conf_code="$WORKING_DAYS_CONF"                \
            --payment_kind=receivable                       \
            --journal_methods=sepa

    check_modules "account_payment_sepa_cog" &&             \
        coog chain -- account_payment_sepa_cog payment      \
            --treatment_date="$TODAY_DATE"                  \
            --payment_kind=payable                          \
            --journal_methods=sepa

    check_modules "account_payment_cog" &&                  \
        coog chain -- account_payment_cog payment_ack       \
            --treatment_date="$TODAY_DATE"                  \
            --journal_methods=sepa

    check_modules "account_aggregate" &&                    \
        coog chain -- account_aggregate snapshot

    check_modules "account_aggregate" &&                    \
        coog chain -- account_aggregate extract_snapshot    \
            --treatment_date="$TODAY_DATE"                  \
            --output_filename="$SNAPSHOT_OUTPUT"

    check_modules "planned_event" &&                        \
        coog chain -- planned_event process                 \
            --treatment_date="$TODAY_DATE"

    check_modules "document_request" &&                     \
        coog chain -- document_request document_process     \
        --treatment_date="$TODAY_DATE"                      \
        --on_model="contract"

    check_modules "report_engine" &&                        \
        coog chain -- report_engine produce_request
fi
