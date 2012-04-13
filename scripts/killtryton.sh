#!/bin/sh

kill -9 $(ps aux | grep "python $TRYTON_PATH/tryton" | awk '{ print $2 }')
kill -9 $(ps aux | grep "python $TRYTOND_PATH/trytond" | awk '{ print $2 }')
