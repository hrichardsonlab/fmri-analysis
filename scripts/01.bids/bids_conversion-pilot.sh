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

# define directories
dataDir="/EBC/rawData/TEBC-5y"									# location of raw data
toolDir="/EBC/processing/tools"									# location of shared tools (dcm2bids)
bidsDir="/EBC/preprocessedData/TEBC-5y/BIDs_data/pilot" 		# BIDs_data has some modifications to the diffusion data
tmpDir="${bidsDir}/tmp"											# temporary directory to transfer raw data to for BIDS conversion

# define number of dicoms per functional run for data checking
pixar_dicoms=324
sesame_dicoms=394

# define config file to use for bids conversion
config=${toolDir}/dcm2bids/TEBC-5Y_config_file-pilot.json

# create BIDS directories if they don't exist
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
			
			cp -R ${dataDir}/${ORIGINALNAME} ${tmpDir}
			
			# remove some of the DTI directories
			rm -R ${tmpDir}/${ORIGINALNAME}/*/*_DTI_AP_*/
			
			# identify all functional runs
			pixar_runs=$(ls -d ${tmpDir}/${ORIGINALNAME}/*/*_pixar*/)
			sesame_runs=$(ls -d ${tmpDir}/${ORIGINALNAME}/*/*_sesame*/)
			
			# check pixar data
			for pr in ${pixar_runs}
			do
				echo "Checking pixar run" ${pr}
			
				# check whether run has too few dicoms and if so remove prior to conversion
				if [ ! "$(ls ${pr} | wc -l)" = ${pixar_dicoms} ] 
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
				if [ ! "$(ls ${sr} | wc -l)" = ${sesame_dicoms} ] 
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
			
			# the sequence names were different for first pilot participant so a different config file is required
			if [ ${NEWNAME} == "001" ] # if first subject
			then
				echo "Processing sub-001 using different configuration file"
				echo
				
				dcm2bids -d ${tmpDir}/${ORIGINALNAME}/*/ -p ${NEWNAME} -s 01 -c ${toolDir}/dcm2bids/TEBC-5Y_config_file-sub-001.json -o ${tmpDir}
			else
				# convert to BIDS [more options: dcm2bids --help]
					# -d: directory with dicom data
					# -p: participant ID
					# -s: session ID
					# -c: configuration file
					# -o: output directory
				dcm2bids -d ${tmpDir}/${ORIGINALNAME}/*/ -p ${NEWNAME} -s 01 -c ${config} -o ${tmpDir}
			fi
			
			# deactivate conda environment
			conda deactivate
			
			# if participant only has 1 run of pixar data, rename to run-01 (default is no run info)
			if [ -f ${tmpDir}/sub-${NEWNAME}/ses-01/func/sub-${NEWNAME}_ses-01_task-pixar_bold.nii.gz ]
			then
				# remame files
				mv ${tmpDir}/sub-${NEWNAME}/ses-01/func/sub-${NEWNAME}_ses-01_task-pixar_bold.nii.gz ${tmpDir}/sub-${NEWNAME}/ses-01/func/sub-${NEWNAME}_ses-01_task-pixar_run-01_bold.nii.gz
				mv ${tmpDir}/sub-${NEWNAME}/ses-01/func/sub-${NEWNAME}_ses-01_task-pixar_bold.json ${tmpDir}/sub-${NEWNAME}/ses-01/func/sub-${NEWNAME}_ses-01_task-pixar_run-01_bold.json
			fi
			
			# remove tmp conversion directories
			rm -R ${tmpDir}/tmp_dcm2bids
			rm -R ${tmpDir}/${ORIGINALNAME}
			
			# copy original BIDS data to BIDS_data folder
			cp -r ${tmpDir}/sub-${NEWNAME} ${bidsDir}
			
			# remove the default diffusion data files
			rm ${bidsDir}/sub-${NEWNAME}/ses-01/dwi/*.nii.gz
			rm ${bidsDir}/sub-${NEWNAME}/ses-01/dwi/*.bv*
			
			# generate new diffusion files
			/EBC/local/MRtrix3_stable/mrtrix3/bin/dwiextract ${tmpDir}/sub-${NEWNAME}/ses-01/dwi/sub-${NEWNAME}_ses-01_dwi.nii.gz -fslgrad ${tmpDir}/sub-${NEWNAME}/ses-01/dwi/sub-${NEWNAME}_ses-01_dwi.bvec ${tmpDir}/sub-${NEWNAME}/ses-01/dwi/sub-${NEWNAME}_ses-01_dwi.bval -shells 0,500,1000,2000 ${bidsDir}/sub-${NEWNAME}/ses-01/dwi/sub-${NEWNAME}_ses-01_dwi.nii.gz -export_grad_fsl ${bidsDir}/sub-${NEWNAME}/ses-01/dwi/sub-${NEWNAME}_ses-01_dwi.bvec ${bidsDir}/sub-${NEWNAME}/ses-01/dwi/sub-${NEWNAME}_ses-01_dwi.bval
			
			# give other users permissions to the generated folder
			chmod -R a+rwx ${bidsDir}/sub-${NEWNAME}
			
		fi
	
done <$1

# remove temporary data conversion directory
rm -r ${tmpDir}
