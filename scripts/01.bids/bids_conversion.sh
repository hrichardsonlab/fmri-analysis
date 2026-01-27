#!/bin/bash

################################################################################
# CONVERT DICOM DATA TO BIDS FORMAT
#
# The dcm2bids singularity was installed using the following code:
# 	APPTAINER_TMPDIR=/RichardsonLab/processing APPTAINER_CACHEDIR=/RichardsonLab/processing sudo apptainer pull /RichardsonLab/processing/singularity_images/dcm2bids.simg docker://unfmontreal/dcm2bids:3.2.0
#
################################################################################

# usage documentation - shown if no text file is provided
Usage() {
	echo
	echo "Usage:"
	echo "./bids_conversion.sh <config file> <list of subject folders to convert>"
	echo
	echo "Example:"
	echo "./bids_conversion.sh config-AWE1_emo-phys.tsv RLABAWE1_subjs.txt"
	echo 
	echo "RLABAWE1_subjs.txt is a file containing the participants to convert"
	echo "RLAB_AWE1_01"
	echo "RLAB_AWE1_02"
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
	echo "./bids_conversion.sh config-AWE1_emo-phys.tsv RLABAWE1_subjs.txt"
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
	echo "./bids_conversion.sh config-AWE1_emo-phys.tsv RLABAWE1_subjs.txt"
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
sharedDir=$(awk -F'\t' '$1=="sharedDir"{print $2}' "$config")
bidsDir=$(awk -F'\t' '$1=="bidsDir"{print $2}' "$config")
rawDir=$(awk -F'\t' '$1=="rawDir"{print $2}' "$config")

# strip extra formatting if present
sharedDir="${sharedDir%$'\r'}"
bidsDir="${bidsDir%$'\r'}"
rawDir="${rawDir%$'\r'}"

# define temporary directory to transfer raw data to for BIDS conversion 
tmpDir="${bidsDir}/tmp"

# extract study name from bidsDir (used to map to correct dcm2bids config file)
study=$(basename "${bidsDir}")

# create BIDS directory if it doesn't exist
if [ ! -d ${bidsDir} ]
then
	mkdir -p ${bidsDir}
fi

# make a temporary directory if it doesn't exist
if [ ! -d ${tmpDir} ]
then
	mkdir -p ${tmpDir}
fi

# create dataset description file if it doesn't exist
if [ ! -f ${bidsDir}/dataset_description.json ]
then
	echo '{' >> ${bidsDir}/dataset_description.json
	echo ' "Name": "RichardsonLab AWE Study 1",' >> ${bidsDir}/dataset_description.json
	echo ' "BIDSVersion": "1.9.0",' >> ${bidsDir}/dataset_description.json
	echo ' "License": ["This dataset is made available under the Public Domain Dedication and License v1.0, whose full text can be found at http://www.opendatacommons.org/licenses/pddl/1.0/. We hope that all users will follow the ODC Attribution/Share-Alike Community Norms (http://www.opendatacommons.org/norms/odc-by-sa/); in particular, while not legally required, we hope that all users of the data will acknowledge the OpenfMRI project and NSF Grant OCI-1131441 (R. Poldrack, PI) in any publications."]' >> ${bidsDir}/dataset_description.json
	echo '}' >> ${bidsDir}/dataset_description.json
fi

# change the location of the singularity cache ($HOME/.singularity/cache by default, but limited space in this directory)
export APPTAINER_TMPDIR=${singularityDir}
export APPTAINER_CACHEDIR=${singularityDir}
unset PYTHONPATH

# display subjects
echo
echo "Converting data to BIDS format in" ${rawDir} "for..."
echo "${subjs}"
echo

# define number of dicoms per functional run for data checking
awe_dicoms=150			# variable number of volumes in complete runs, so just set this to a reasonable estimate
tomloc_dicoms=141		# 214 in complete run
langloc_dicoms=172		# 260 in complete run
pixar_dicoms=111		# 168 in complete run
snackattack_dicoms=93	# 140 in complete run

# iterate for all subjects in the text file
while read p
do
	raw_name=` basename ${p} | awk -F- '{print $NF}' `	# raw subj name
	bids_name=$(echo "$raw_name" | tr -d '_ ') # bids formatted subj name
	
	# convert data if the subject has a raw data folder, trying different naming conventions to check whether the folder exists
	if [ -d ${rawDir}/${raw_name} ]
	then
	
		# copy rawData to temporary directory
		echo "Copying ${raw_name} to temporary directory within BIDS folder for conversion"
		echo
		
		cp -r ${rawDir}/${raw_name} ${tmpDir}
		
		# remove SBRef files
		rm -r ${tmpDir}/${raw_name}/*/*_SBRef
		
		# identify all functional runs
		awe_runs=$(ls -d ${tmpDir}/${raw_name}/*/*_awe*/)
		tomloc_runs=$(ls -d ${tmpDir}/${raw_name}/*/*_tomloc*/)
		langloc_runs=$(ls -d ${tmpDir}/${raw_name}/*/*_langloc*/)
		pixar_runs=$(ls -d ${tmpDir}/${raw_name}/*/*_pixar*/)
		snackattack_runs=$(ls -d ${tmpDir}/${raw_name}/*/*_snack*/)
		
		# check awe data
		for a in ${awe_runs}
		do
			echo "Checking awe run" ${a}
		
			# check whether run has too few dicoms and if so remove prior to conversion
			if [[ ! "$(ls ${a} | wc -l)" -ge ${awe_dicoms} ]]
			then
				echo
				echo ${a} "is an incomplete run and will be excluded from BIDS conversion"
				echo
				rm -r ${a}
			fi
		done
		
		# check tomloc data
		for t in ${tomloc_runs}
		do
			echo "Checking tomloc run" ${t}
		
			# check whether run has too few dicoms and if so remove prior to conversion
			if [[ ! "$(ls ${t} | wc -l)" -ge ${tomloc_dicoms} ]]
			then
				echo
				echo ${t} "is an incomplete run and will be excluded from BIDS conversion"
				echo
				rm -r ${t}
			fi
		done
		
		# check langloc data
		for l in ${langloc_runs}
		do
			echo "Checking langloc run" ${l}
		
			# check whether run has too few dicoms and if so remove prior to conversion
			if [[ ! "$(ls ${l} | wc -l)" -ge ${langloc_dicoms} ]]
			then
				echo
				echo ${l} "is an incomplete run and will be excluded from BIDS conversion"
				echo
				rm -r ${l}
			fi
		done
		
		# check pixar data
		for p in ${pixar_runs}
		do
			echo "Checking pixar run" ${p}
		
			# check whether run has too few dicoms and if so remove prior to conversion
			if [[ ! "$(ls ${p} | wc -l)" -ge ${pixar_dicoms} ]]
			then
				echo
				echo ${p} "is an incomplete run and will be excluded from BIDS conversion"
				echo
				rm -r ${p}
			fi
		done
		
		# check snackattack data
		for s in ${snackattack_runs}
		do
			echo "Checking snackattack run" ${s}
		
			# check whether run has too few dicoms and if so remove prior to conversion
			if [[ ! "$(ls ${s} | wc -l)" -ge ${snackattack_dicoms} ]]
			then
				echo
				echo ${s} "is an incomplete run and will be excluded from BIDS conversion"
				echo
				rm -r ${s}
			fi
		done
		
		# BIDS conversion
		echo
		echo "Converting sub-${bids_name} to BIDS"
		echo
		
		echo "${sharedDir}/dcm2bids_files/${study}_config.json"
		
		# convert to BIDS [more options: dcm2bids --help]
			# -d: directory with dicom data
			# -p: participant ID
			# -s: session ID (none)
			# -c: configuration file
			# -o: output directory
		apptainer exec -B /RichardsonLab:/RichardsonLab,/${bidsDir}:/${bidsDir}		\
		  ${singularityDir}/dcm2bids.simg											\
		  dcm2bids																	\
			-d ${tmpDir}/${raw_name}												\
			-p sub-${bids_name}														\
			-c ${sharedDir}/dcm2bids_files/${study}/sub-${bids_name}_config.json	\
			-o ${tmpDir}
		
		# remove tmp conversion directories
		rm -r ${tmpDir}/tmp_dcm2bids
		rm -r ${tmpDir}/${raw_name}
		
		# copy temporary folder to BIDS folder
		mv ${tmpDir}/sub-${bids_name} ${bidsDir}
		
		# remove BIDS URL from fieldmap json files because these aren't recognized by fMRIPrep
		grep -l '"IntendedFor"' ${bidsDir}/sub-${bids_name}/fmap/*.json | xargs sed -i 's/bids::sub-[^/]*\///g'
		
	fi
	
done <$2

# remove temporary data conversion directory
rm -r ${tmpDir}
