#!/bin/bash

bidsanon=$1
subject=$2

cd $bidsanon/$subject/anat

for x in *.nii.gz; do
    echo $x
    if [[ $x == *"defaced.nii.gz" ]]; then
        echo "already defaced $subject, no undefaced file present"
		mv -- "$x" "${x/%_defaced.nii.gz/.nii.gz}"
        continue
    fi
    echo defacing $subject now
    pydeface "$x"
    if ls *defaced.nii.gz 1> /dev/null 2>&1; then # if defaced file does exist
        echo file defaced successfully, removing original file
        rm -f "$x"
        # removing "_defaced" string from filename
        if [[ $i == *"defaced.nii.gz" ]]; then
		    mv -- "$i" "$x"
        fi 
    fi
done

