#!/bin/bash

################################################################################
# DELETE FIRSTLEVEL OUTPUT FILES
#
################################################################################

# usage documentation - shown if no PATH.txt file is found
Usage() {
	echo
	echo
	echo "Usage:"
	echo "./delete_firstlevel_outputs.sh <config file name> <subject list>"
	echo
	echo "Example:"
	echo "./delete_firstlevel_outputs.sh config-awe_emo-phys.tsv RLABAWE1_subjs.txt"
	echo
	echo "The config file name (not path!) should be provided"
	echo
	echo "RLABAWE1_subjs.txt is a subject file containing the participants to process:"
	echo "sub-RLABAWE101"
	echo "sub-RLABAWE102"
	echo "..."
	echo
	echo "The use case of this script is when firstlevel modelling has been run, but updates" 
	echo "have been made to the requested contrasts and the firstlevel modelling"
	echo "needs to be re-run. The firstlevel modelling script will not delete the prior outputs"
	echo "which can cause issues if you've change the contrast order because the returned copes"
	echo "files may clash with the new contrast order."
	echo
	echo "In this scenario, it is best practice to either:"
	echo "(1) delete the prior model and design outputs"
	echo "(2) re-run the script but have the pipeline output the results to a new timestamped folder"
	echo "(3) set 'overwrite' to 'yes' in your config file and leave the resultsDir field blank."
	echo
	echo "Note that option (3) will delete *everything* in your current results folder, so this might"
	echo "only be a good option if other analysis outputs (e.g., timecourses, extracted stats)"
	echo "have not been generated."
	echo
	echo "This script will look for a PATHS.txt file saved 2 directories above where this script is saved"
	echo
	echo
	echo "Script created by Melissa Thye"
	echo
	exit
}
[ "$1" = "" ]| [ "$2" = "" ] && Usage

if [ ! -f ../../PATHS.txt ]
	then Usage
fi

if [ ! ${1##*.} == "tsv" ]
then
	echo
	echo "The configuration file was not found."
	echo "The script must be submitted with (1) a configuration file name and (2) a subject list as in the example below."
	echo
	echo "./delete_firstlevel_outputs.sh config-awe_emo-phys.tsv RLABAWE1_subjs.txt"
	echo
	
	# end script and show full usage documentation	
	Usage
fi

if [ ! ${2##*.} == "txt" ]
then
	echo
	echo "The list of participants was not found."
	echo "The script must be submitted with (1) a configuration file name and (2) a subject list as in the example below."
	echo
	echo "./delete_firstlevel_outputs.sh config-awe_emo-phys.tsv RLABAWE1_subjs.txt"
	echo
	
	# end script and show full usage documentation	
	Usage
fi

# define directories
projDir=`cat ../../PATHS.txt`

# define config file and subjects from files passed in script call
config=${projDir}/$1
subjs=$(cat $2 | awk '{print $1}')

# define data directories depending on study information
resultsDir=$(awk -F'\t' '$1=="resultsDir"{print $2}' "$config")

# strip extra formatting if present
resultsDir="${resultsDir%$'\r'}"

# display subjects
echo
echo "Deleting firstlevel modelling outputs in" ${resultsDir} "for..."
echo "${subjs}"
echo

# search for model directories to clean up
for dir in $(ls -d ${resultsDir}/sub-*)
do
	if [ -d ${dir%/}/model ]
	then
		echo "Deleting ${dir%/}/model"
		
		rm -r ${dir%/}/model
	fi

done

# search for design directories to clean up
for dir in $(ls -d ${resultsDir}/sub-*)
do
	if [ -d ${dir%/}/design ]
	then
		echo "Deleting ${dir%/}/design"
		
		rm -r ${dir%/}/design
	fi

done