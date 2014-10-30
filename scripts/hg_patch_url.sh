#!/bin/bash
#
# Dependencies:
# -------------
#   apt-get install xsel
#
# Usage
# -----
# On rietveld issue page, click on the [raw] link to access the diff page
# eg http://rietveld.coopengo.com/download/issue3350001_70001.diff
# Copy the page (Ctrl+A, Ctrl+C)
# In your terminal :
#       hg_patch_url.sh

TMP_DIFF=`mktemp --suffix=.diff`
xsel --clipboard > $TMP_DIFF
grep "^GIT binary patch$" $TMP_DIFF > /dev/null
if [[ $? == 0 ]];
then
    # I can imagine big binary data leading to clipboard overflow ?!?...
    echo "Patch containing binary diff. Better be safe than sorry, exiting."
    return
fi
echo "----------------------"
cat $TMP_DIFF
echo -e "\n----------------------"
echo -e "\nApply this patch?"
select yn in "Yes" "No"; do
    case $yn in
        Yes ) hg patch --no-commit $TMP_DIFF; break;;
        No ) echo "Patch rejected by user"; break;;
    esac
done
rm -f $TMP_DIFF
