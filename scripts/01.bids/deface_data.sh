#!/bin/bash

################################################################################
# DEFACE BIDS FORMATTED DATA
#
# The dcm2bids singularity (which contains pydeface) was installed using the following code:
# 	APPTAINER_TMPDIR=/RichardsonLab/processing APPTAINER_CACHEDIR=/RichardsonLab/processing sudo apptainer pull /RichardsonLab/processing/singularity_images/dcm2bids.simg docker://unfmontreal/dcm2bids:3.2.0
#
################################################################################

# usage documentation - shown if no text file is provided
Usage() {
	echo
	echo "Usage:"
	echo "./deface_data.sh <config file> <list of subjects to deface>"
	echo
	echo "Example:"
	echo "./deface_data.sh config-awe1_emo-phys.tsv RLABAWE1_subjs.txt"
	echo 
	echo "RLABAWE1_subjs.txt is a file containing the participants to convert"
	echo "sub-RLABAWE101"
	echo "sub-RLABAWE102"
	echo "..."
	echo
	echo
	echo "Script created by Melissa Thye"
	echo
	exit
}
[ "$1" = "" ] | [ "$2" = "" ] && Usage

# if the script is run outside of the RichardsonLab directory (e.g., in home directory where space is limited), terminate the script and show usage documentation
if [[ ! "$PWD" =~ "/RichardsonLab/" ]]; 
then Usage
fi

if [ ! ${1##*.} == "tsv" ]
then
	echo
	echo "The configuration file was not found."
	echo "The script must be submitted with (1) a configuration file name and (2) a subject-run list as in the example below."
	echo
	echo "./deface_data.sh config-awe1_emo-phys.tsv RLABAWE1_subjs.txt"
	echo	
	# end script and show full usage documentation	
	Usage
fi

if [ ! ${2##*.} == "txt" ]
then
	echo
	echo "The list of participants was not found."
	echo "The script must be submitted with (1) a configuration file name and (2) a subject-run list as in the example below."
	echo
	echo "./deface_data.sh config-awe1_emo-phys.tsv RLABAWE1_subjs.txt"
	echo	
	# end script and show full usage documentation	
	Usage
fi

# define directories
projDir=`cat ../../PATHS.txt`
singularityDir="${projDir}/singularity_images"

# define config file and subjects from files passed in script call
config=${projDir}/$1
subjs=$(cat $2 | awk '{print $1}')

# define BIDS directory depending on path provided in config file
bidsDir=$(awk -F'\t' '$1=="bidsDir"{print $2}' "$config")

# strip extra formatting if present
bidsDir="${bidsDir%$'\r'}"

# change the location of the singularity cache ($HOME/.singularity/cache by default, but limited space in this directory)
export APPTAINER_TMPDIR=${singularityDir}
export APPTAINER_CACHEDIR=${singularityDir}
unset PYTHONPATH

# display subjects
echo
echo "Defacing data in" ${bidsDir} "for..."
echo "${subjs}"
echo

# iterate for all subjects in the text file
while read sub
do
	# deface data if the subject has a BIDS data folder
	if [ -d ${bidsDir}/${sub} ]
	then
		# list all anatomical files to deface (typically just a single T1w file)
		files=$(find ${bidsDir}/${sub} -type f \( -path "*/anat/*.nii.gz" \) | sort)
		
		# optionally list anatomical and functional files
		#files=$(find ${bidsDir}/${sub} -type f \( -path "*/anat/*.nii.gz" -o -path "*/func/*.nii.gz" \) | sort)
		
		for f in ${files}
		do
		
		echo "Defacing" ${f}
	
		# run pydeface within dcm2bids singularity
		apptainer exec -B ${bidsDir}:/${bidsDir}	\
		  ${singularityDir}/dcm2bids.simg			\
		  pydeface ${f}								\
		  --outfile ${f}							\
		  --force
		  
		done
	
	# if no BIDS folder found for this subject	
	else
		echo "No BIDS data found for" ${sub}
	fi
	
done <$2
