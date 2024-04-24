#!/bin/bash

################################################################################
# CONVERT DICOM DATA TO BIDS FORMAT
################################################################################

# usage documentation - shown if no text file is provided
Usage() {
    echo
    echo "Usage:"
    echo "./bids_conversion.sh <list of subject folders to convert>"
    echo
    echo "Example:"
    echo "./bids_conversion.sh list.txt"
    echo 
    echo "list.txt is a file containing the name of the raw data folders to convert"
    echo "TEBC-5Y-8035"
    echo "TEBC-5Y-8036"
	echo "..."
    echo
	echo
    echo "Script created by Manuel Blesa & Melissa Thye"
    echo
    exit
}
[ "$1" = "" ] && Usage

# indicate whether session folders are used (always 'yes' for EBC data)
sessions='yes'

# extract sample from list of subjects filename (i.e., are these pilot or HV subjs)
sample=` basename $1 | cut -d '-' -f 3 | cut -d '.' -f 1 `
cohort=` basename $1 | cut -d '_' -f 1 `

# define location of shared tools (dcm2bids)
toolDir="/EBC/processing/tools"

# define data directories depending on sample information
if [[ ${sample} == 'pilot' ]]
then
	# define data directories
	dataDir="/EBC/rawData/${cohort}"
	bidsDir="/EBC/preprocessedData/${cohort}/BIDs_data/pilot"
	
	# define config file to use for bids conversion
	config=${toolDir}/dcm2bids/${cohort}_config_file-pilot.json
elif [[ ${sample} == 'HV' ]]
then
	# define data directories
	dataDir="/EBC/rawData/${cohort}-adultpilot"
	bidsDir="/EBC/preprocessedData/${cohort}-adultpilot/BIDs_data"
	# define config file to use for bids conversion
	config=${toolDir}/dcm2bids/${cohort}_config_file.json
else
	# define data directories
	dataDir="/EBC/rawData/${cohort}"
	bidsDir="/EBC/preprocessedData/${cohort}/BIDs_data"
	# define config file to use for bids conversion
	config=${toolDir}/dcm2bids/${cohort}_config_file.json
fi

# define temporary directory to transfer raw data to for BIDS conversion 
tmpDir="${bidsDir}/tmp"

# print confirmation of sample and directory
echo 'Converting' ${sample} 'data to BIDS format in' ${bidsDir}

# define number of dicoms per functional run for data checking
pixar_dicoms=214  # 324 in complete run
sesame_dicoms=260 # 394 in complete run

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
	echo ' "BIDSVersion": "1.0.0",' >> ${bidsDir}/dataset_description.json
	echo ' "License":"This dataset is made available under the Public Domain Dedication and License \nv1.0, whose full text can be found at \nhttp://www.opendatacommons.org/licenses/pddl/1.0/. \nWe hope that all users will follow the ODC Attribution/Share-Alike \nCommunity Norms (http://www.opendatacommons.org/norms/odc-by-sa/); \nin particular, while not legally required, we hope that all users \nof the data will acknowledge the OpenfMRI project and NSF Grant \nOCI-1131441 (R. Poldrack, PI) in any publications.",' >> ${bidsDir}/dataset_description.json
	echo ' "Name": "TheirWorld Edinburgh Birth Cohort (TEBC)",' >> ${bidsDir}/dataset_description.json
	echo ' "ReferencesAndLinks": ["Boardman JP, Hall J, Thrippleton MJ, Reynolds RM, Bogaert D, Davidson DJ, Schwarze J, Drake AJ, Chandran S, Bastin ME, et al. 2020. Impact of preterm birth on brain development and long-term outcome: protocol for a cohort study in Scotland. BMJ Open.  10. doi: 10.1136/bmjopen-2019-035854."]' >> ${bidsDir}/dataset_description.json
	echo '}' >> ${bidsDir}/dataset_description.json
fi

# iterate for all subjects in the text file
while read p
do
	ORIGINALNAME=` basename ${p} | cut -d '_' -f 1 `	# raw data folder name
	NEWNAME=` basename ${p} | awk -F- '{print $NF}' `	# subj number from folder name

		if [ -d ${dataDir}/${ORIGINALNAME} ] # if the subject has a raw data folder
		then
			
			# copy rawData to temporary directory
			echo
			echo "Copying ${ORIGINALNAME} to temporary directory within BIDS_data folder for conversion"
			echo
			
			cp -r ${dataDir}/${ORIGINALNAME} ${tmpDir}
			
			# remove some of the DTI directories
			rm -r ${tmpDir}/${ORIGINALNAME}/*/*_DTI_AP_*/
			
			# identify all functional runs
			pixar_runs=$(ls -d ${tmpDir}/${ORIGINALNAME}/*/*_pixar*/)
			sesame_runs=$(ls -d ${tmpDir}/${ORIGINALNAME}/*/*_sesame*/)
			
			# check pixar data
			for pr in ${pixar_runs}
			do
				echo "Checking pixar run" ${pr}
			
				# check whether run has too few dicoms and if so remove prior to conversion
				if [[ ! "$(ls ${pr} | wc -l)" -ge ${pixar_dicoms} ]]
				then
					echo
					echo ${pr} "is an incomplete run and will be excluded from BIDS conversion"
					echo
					rm -r ${pr}
				fi
			done
			
			# check sesame data
			for sr in ${sesame_runs}
			do
				echo "Checking sesame run" ${sr}
			
				# check whether run has too few dicoms and if so remove prior to conversion
				if [[ ! "$(ls ${sr} | wc -l)" -ge ${sesame_dicoms} ]]
				then
					echo
					echo ${sr} "is an incomplete run and will be excluded from BIDS conversion"
					echo
					rm -r ${sr}
				fi
			done

			# BIDS conversion
			echo
			echo "Converting subject ${ORIGINALNAME} to BIDS and renaming to ${NEWNAME}"
			echo
			
			# activate conda environment via bash
			eval "$(conda shell.bash hook)"
			conda activate ${toolDir}/dcm2bids
			
			# convert to BIDS [more options: dcm2bids --help]
				# -d: directory with dicom data
				# -p: participant ID
				# -s: session ID
				# -c: configuration file
				# -o: output directory
			if [[ ${sessions} == 'yes' ]]
			then
				dcm2bids -d ${tmpDir}/${ORIGINALNAME}/*/ -p ${NEWNAME} -s 01 -c ${config} -o ${tmpDir}
				subDir="sub-${NEWNAME}/ses-01"
				file_prefix="sub-${NEWNAME}_ses-01"
			else
				dcm2bids -d ${tmpDir}/${ORIGINALNAME}/*/ -p ${NEWNAME} -c ${config} -o ${tmpDir}
				subDir="sub-${NEWNAME}"
				file_prefix="sub-${NEWNAME}"
			fi
			
			# deactivate conda environment
			conda deactivate
			
			# if participant only has 1 run of pixar data, rename to run-01 (default is no run info)
			if [ -f ${tmpDir}/${subDir}/func/${file_prefix}_task-pixar_bold.nii.gz ]
			then
				# remame files
				mv ${tmpDir}/${subDir}/func/${file_prefix}_task-pixar_bold.nii.gz ${tmpDir}/${subDir}/func/${file_prefix}_task-pixar_run-01_bold.nii.gz
				mv ${tmpDir}/${subDir}/func/${file_prefix}_task-pixar_bold.json ${tmpDir}/${subDir}/func/${file_prefix}_task-pixar_run-01_bold.json
			fi
			
			# remove tmp conversion directories
			rm -R ${tmpDir}/tmp_dcm2bids
			rm -R ${tmpDir}/${ORIGINALNAME}
			
			# copy temporary folder to BIDS_data folder
			cp -r ${tmpDir}/sub-${NEWNAME} ${bidsDir}
			
			# remove the default diffusion data files
			rm ${bidsDir}/${subDir}/dwi/*.nii.gz
			rm ${bidsDir}/${subDir}/dwi/*.bv*
			
			# generate new diffusion files
			/EBC/local/MRtrix3_stable/mrtrix3/bin/dwiextract ${tmpDir}/${subDir}/dwi/${file_prefix}_dwi.nii.gz -fslgrad ${tmpDir}/${subDir}/dwi/${file_prefix}_dwi.bvec ${tmpDir}/${subDir}/dwi/${file_prefix}_dwi.bval -shells 0,500,1000,2000 ${bidsDir}/${subDir}/dwi/${file_prefix}_dwi.nii.gz -export_grad_fsl ${bidsDir}/${subDir}/dwi/${file_prefix}_dwi.bvec ${bidsDir}/${subDir}/dwi/${file_prefix}_dwi.bval
			
			# give other users permissions to the generated folder
			chmod -R a+rwx ${bidsDir}/sub-${NEWNAME}
		
		fi
	
done <$1

# remove temporary data conversion directory
rm -r ${tmpDir}
