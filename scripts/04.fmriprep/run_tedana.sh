#!/bin/bash

################################################################################
# SUBMIT FMRIPREP PREPROCESSED MULTIECHO DATA TO TEDANA TO DENOISE
#
# This script takes the preprocessed multi-echos output from fmriprep and (1) runs them through
# tedana to denoise and optimally recombine them and (2) normalize the data to MNI space
#
# The nipype singularity was installed using the following code:
# 	SINGULARITY_TMPDIR=/EBC/processing SINGULARITY_CACHEDIR=/EBC/processing singularity build /EBC/processing/singularity_images/nipype-1.8.6.simg docker://nipype/nipype:latest
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
	echo "./run_tedana.sh Narrative_Comprehension-subjs.txt"
	echo
	echo "Narrative_Comprehension-subjs.txt is a file containing the participants to check:"
	echo "001"
	echo "002"
	echo "..."
	echo
	echo "Script created by Melissa Thye"
	echo
	exit
}
[ "$1" = "" ] && Usage

if [ ! ${1##*.} == "txt" ]
then
	echo
	echo "The list of participants was not found."
	echo "The script must be submitted with a subject list as in the example below."
	echo
	echo "./run_tedana.sh Narrative_Comprehension-subjs.txt"
	echo
	
	# end script and show full usage documentation	
	Usage
fi

# indicate whether session folders are used
sessions='no'

# define subjects from text document
subjs=$(cat $1 | awk '{print $1}') 

# extract sample from list of subjects filename
study=` basename $1 | cut -d '-' -f 1 `

# define data directories depending on sample information
bidsDir="/projects/${study}/BIDS"
derivDir="${bidsDir}/derivatives"

# define directories
projDir=`cat ../../PATHS.txt`
singularityDir="${projDir}/singularity_images"
codeDir="${projDir}/scripts/03.fmriprep"

# convert the singularity image to a sandbox if it doesn't already exist to avoid having to rebuild on each run
# if [ ! -d ${singularityDir}/nipype_sandbox ]
# then
	# singularity build --sandbox ${singularityDir}/nipype_sandbox ${singularityDir}/nipype_nilearn.simg
# fi

# change the location of the singularity cache ($HOME/.singularity/cache by default, but limited space in this directory)
export SINGULARITY_TMPDIR=${singularityDir}
export SINGULARITY_CACHEDIR=${singularityDir}
unset PYTHONPATH

# run singularity to submit tedana script
singularity exec -C -B /archive:/archive -B /projects:/projects -B ${projDir}:${projDir}	\
${singularityDir}/nipype_nilearn.simg							\
/neurodocker/startup.sh python ${codeDir}/denoise_echos.py		\
-s ${subjs}														\
-n ${sessions}													\
-b ${bidsDir}													\
-d ${derivDir}													\
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
	T1w_MNI_transform=${subDir_deriv}/anat/*from-T1w_to-MNI152NLin2009cAsym_mode-image_xfm.h5
	
	# for each task
	for t in ${tasks}
	do
		echo
		echo "Normalizing ${t} tedana outputs for sub-${sub}"
		echo
		
		# grab denoised and transform files
		denoised_img=${subDir_deriv}/func/tedana/${t}/*_desc-denoised_bold.nii.gz
		reference_img=${subDir_deriv}/func/*${t}*MNI152NLin2009cAsym_res-2_boldref.nii.gz
		native_T1w_transform=${subDir_deriv}/func/*${t}*from-boldref_to-T1w_mode-image_desc-coreg_xfm.txt
		
		# define output file
		normalized_img=${subDir_deriv}/func/tedana/${t}/sub-${sub}_task-${t}_space-MNI152NLin2009cAsym_res-2_desc-denoised_bold.nii.gz
	
		singularity exec -C -B /archive:/archive -B /projects:/projects -B ${projDir}:${projDir}	\
		${singularityDir}/fmriprep-24.0.0.simg 														\
		antsApplyTransforms -e 3 																	\
							-i ${denoised_img} 														\
							-r ${reference_img}														\
							-o ${normalized_img}													\
							-n LanczosWindowedSinc													\
							-t ${native_T1w_transform}												\
							   ${T1w_MNI_transform} 											
							   
	done
	
done <$1