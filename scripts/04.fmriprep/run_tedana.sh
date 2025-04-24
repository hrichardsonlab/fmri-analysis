#!/bin/bash

################################################################################
# SUBMIT FMRIPREP PREPROCESSED MULTIECHO DATA TO TEDANA TO DENOISE
#
# This script:
# (1) generates a combined grey + white matter mask, registers this mask to EPI space, and combines the mask with the BOLD mask for optimal coverage of ventral ATL
# (2) rus the preprocessed multi-echos output from fmriprep through tedana to denoise and optimally recombine them
# (3) normalizes optimally combined data to MNI space
#
################################################################################

# usage documentation - shown if no text file is provided or if script is run outside EBC directory
Usage() {
	echo
	echo
	echo "Usage:"
	echo "./run_tedana.sh <list of subjects>"
	echo
	echo "Example:"
	echo "./run_tedana.sh fMRI_Semantics-subjs.txt"
	echo
	echo "fMRI_Semantics-subjs.txt is a file containing the participants to check:"
	echo "001"
	echo "002"
	echo "..."
	echo
	echo "Script created by Melissa Thye"
	echo
	exit
}
[ "$1" = "" ] && Usage

# if the script is run outside of the EBC directory (e.g., in home directory where space is limited), terminate the script and show usage documentation
if [[ ! "$PWD" =~ "/EBC/" ]]
then Usage
fi

if [ ! ${1##*.} == "txt" ]
then
	echo
	echo "The list of participants was not found."
	echo "The script must be submitted with a subject list as in the example below."
	echo
	echo "./run_tedana.sh fMRI_Semantics-subjs.txt"
	echo
	
	# end script and show full usage documentation	
	Usage
fi

# indicate whether session folders are used
sessions='yes'

# define subjects from text document
subjs=$(cat $1 | awk '{print $1}') 

# extract sample from list of subjects filename
study=` basename $1 | cut -d '-' -f 1 `

# define data directories depending on sample information
if [[ ${sample} == 'pilot' ]]
then
	bidsDir="/EBC/preprocessedData/${cohort}/BIDs_data/pilot"
	derivDir="/EBC/preprocessedData/${cohort}/derivatives/pilot"
elif [[ ${sample} == 'HV' ]]
then
	bidsDir="/EBC/preprocessedData/${cohort}-adultpilot/BIDs_data"
	derivDir="/EBC/preprocessedData/${cohort}-adultpilot/derivatives"
else
	bidsDir="/EBC/preprocessedData/${cohort}/BIDs_data"
	derivDir="/EBC/preprocessedData/${cohort}/derivatives"
fi

# define directories
projDir=`cat ../../PATHS.txt`
singularityDir="${projDir}/singularity_images"
codeDir="${projDir}/scripts/04.fmriprep"

# convert the singularity image to a sandbox if it doesn't already exist to avoid having to rebuild on each run
# if [ ! -d ${singularityDir}/nipype_sandbox ]
# then
	# singularity build --sandbox ${singularityDir}/nipype_sandbox ${singularityDir}/nipype_nilearn.simg
# fi

# change the location of the singularity cache ($HOME/.singularity/cache by default, but limited space in this directory)
export APPTAINER_TMPDIR=${singularityDir}
export APPTAINER_CACHEDIR=${singularityDir}
unset PYTHONPATH

# run singularity to submit tedana script
apptainer exec -C -B /EBC:/EBC -B ${projDir}:${projDir}		\
${singularityDir}/nipype_nilearn.simg						\
/neurodocker/startup.sh python ${codeDir}/denoise_echos.py	\
-s ${subjs}													\
-n ${sessions}												\
-b ${bidsDir}												\
-d ${derivDir}												\
-c 4

# normalize tedana outputs within fmriprep singularity
# the easier option would be to use the version of ants included in nipype but this version won't read the h5 transform files output by fMRIPrep (more here: https://github.com/nipreps/fmriprep/issues/2756). 
# This might be fixed in the future, so the code to do the normalization in python is commented out in the above denoise_echos.py script in case a future version is compatible (though this would require updating the nipype singularity).
# for the moment, the only workaround is to use the fmriprep singularity image which has a compatible version of ants installed.

# iterate for all subjects in the text file
while read p
do
	sub=` basename ${p} `
	
	# define subject derivatives directory depending on whether data are organized in session folders
	if [[ ${sessions} == 'yes' ]]
	then
		subDir_deriv="${derivDir}/sub-${sub}/ses-01"
	else
		subDir_deriv="${derivDir}/sub-${sub}"
	fi
	
	# extract task names
    tasks=`ls -d ${subDir_deriv}/func/tedana/* | sed -r 's/^.+\///'`
		
    # grab normalized anat transform file
	T1w_MNI_transform=${subDir_deriv}/anat/*from-T1w_to-MNI152NLin2009cAsym*mode-image_xfm.h5
	
	# for each task
	for t in ${tasks}
	do
		echo
		echo "Normalizing ${t} tedana outputs for sub-${sub}"
		echo
		
		# grab denoised and transform files
		denoised_img=${subDir_deriv}/func/tedana/${t}/*_desc-denoised_bold.nii.gz
		reference_img=${subDir_deriv}/func/*${t}*MNI152NLin2009cAsym*_boldref.nii.gz
		native_T1w_transform=${subDir_deriv}/func/*${t}*from-boldref_to-T1w_mode-image_desc-coreg_xfm.txt
		
		# grab combined mask file
		combined_mask=${subDir_deriv}/func/tedana/${t}/*_space-T1w_desc-gmwmbold_mask.nii.gz
		
		# define output files
		normalized_img=${subDir_deriv}/func/tedana/${t}/sub-${sub}_task-${t}_space-MNI152NLin2009cAsym_desc-denoised_bold.nii.gz
		normalized_mask=${subDir_deriv}/func/tedana/${t}/sub-${sub}_task-${t}_space-MNI152NLin2009cAsym_desc-gmwmbold_mask.nii.gz
		
		# normalize tedana denoised data to MNI space
		apptainer exec -C -B /EBC:/EBC -B ${projDir}:${projDir}		\
		${singularityDir}/fmriprep-24.0.0.simg 						\
		antsApplyTransforms -e 3 									\
							-i ${denoised_img} 						\
							-r ${reference_img}						\
							-o ${normalized_img}					\
							-n LanczosWindowedSinc					\
							-t ${native_T1w_transform}				\
							   ${T1w_MNI_transform} 											
							
		# normalize combined grey matter, white matter, bold mask to MNI space
		apptainer exec -C -B /EBC:/EBC -B /projects:/projects -B ${projDir}:${projDir}		\
		${singularityDir}/fmriprep-24.0.0.simg 												\
		antsApplyTransforms -d 3 															\
							-i ${combined_mask} 											\
							-r ${reference_img}												\
							-o ${normalized_mask}											\
							-n NearestNeighbor												\
							-t ${native_T1w_transform}										\
							   ${T1w_MNI_transform} 	
	done
	
done <$1