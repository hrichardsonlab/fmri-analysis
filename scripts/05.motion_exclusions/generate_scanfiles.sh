#!/bin/bash

################################################################################
# GENERATE THE SCANS.TSV FILE THAT WILL BE USED TO MARK RUN EXCLUSIONS
# 
# More information on these files: 
#	https://bids-specification.readthedocs.io/en/stable/modality-agnostic-files.html#scans-file
################################################################################

# usage documentation
Usage() {
	echo
	echo
	echo "Usage:"
	echo "./generate_scanfiles.sh <config file> <list of subjects>"
	echo
	echo "Example:"
	echo "./generate_scanfiles.sh config-awe_emo-phys.tsv RLABPILOT_subjs.txt"
	echo
	echo "RLABPILOT_subjs.txt is a file containing the participants to generate the scans.tsv file for:"
	echo "sub-RLABPILOT01"
	echo "sub-RLABPILOT02"
	echo "..."
	echo
	echo
	echo "Script created by Melissa Thye"
	echo
	exit
}
[ "$1" = "" ] | [ "$2" = "" ] && Usage

# check files passed in script call
if [ ! ${1##*.} == "tsv" ]
then
	echo
	echo "The configuration file was not found."
	echo "The script must be submitted with (1) a configuration file name and (2) a subject list as in the example below."
	echo
	echo "./generate_scanfiles.sh config-awe_emo-phys.tsv RLABPILOT_subjs.txt"
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
	echo "./generate_scanfiles.sh config-awe_emo-phys.tsv RLABPILOT_subjs.txt"
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

# define data directories depending on study information
bidsDir=$(awk -F'\t' '$1=="bidsDir"{print $2}' "$config")
derivDir=$(awk -F'\t' '$1=="derivDir"{print $2}' "$config")
sessions=$(awk -F'\t' '$1=="sessions"{print $2}' "$config")

# strip extra formatting if present
bidsDir="${bidsDir%$'\r'}"
derivDir="${derivDir%$'\r'}"
sessions="${sessions%$'\r'}"

# print confirmation of study and directory
echo 'Generating scans.tsv files for data in' ${derivDir}

# iterate over subjects
while read p
do
	sub=` basename ${p} `
	
	# define subject derivatives directory depending on whether data are organized in session folders
	if [[ ${sessions} == 'yes' ]]
	then
		subDir_bids="${bidsDir}/${sub}/ses-01/func"
		subDir_deriv="${derivDir}/${sub}/ses-01/func"
		scan_file="${sub}_ses-01_scans.tsv"
	else
		subDir_bids="${bidsDir}/${sub}/func"
		subDir_deriv="${derivDir}/${sub}/func"
		scan_file="${sub}_scans.tsv"
	fi

	# create scan.tsv file for each subject who has functional data
	if [ -d ${subDir_bids} ] # if the subject has a functional data folder
	then
		echo "Generating scans.tsv file for ${sub}"

		# delete scans.tsv file if it already exists
		if [ -f ${subDir_bids}/${scan_file} ] || [ -f ${subDir_deriv}/${scan_file} ] 
		then 
			rm ${subDir_bids}/${scan_file}
			rm ${subDir_deriv}/${scan_file}
		fi
		
		# print run info to scan.tsv file
		printf "filename" >>  ${subDir_bids}/${scan_file}
	
		# list of functional files
		files=(`ls ${subDir_bids}/*nii.gz`)
		
		# for each file in the func directory, add filename to scans.tsv file
		for f in ${files[@]}
		do
			# extract file name (remove full path and echo info, if needed)
			current=`basename ${f}`
			current=$(echo "${current}" | sed -E 's/_echo-[0-9]+//')
			
			# skip if the run is already in the list (which will happen for multi-echo data)
			if grep -qx "func/${current}" "${subDir_bids}/${scan_file}"
			then
				continue
			fi

			# add file name (with directory) to scans.tsv file
			name=""
			name='\nfunc/'${current}
			printf ${name} >> ${subDir_bids}/${scan_file}
		
		done
		
	fi
	
	# copy scans.tsv to derivDir
	cp ${subDir_bids}/${scan_file} ${subDir_deriv}/${scan_file}
	
done <$2

