#!/bin/bash

################################################################################
# RUN FMRIPREP ON BIDS DATA ALREADY RUN THROUGH FREESURFER
#
# The fMRIPrep singularity was installed using the following code:
# 	SINGULARITY_TMPDIR=/data/EBC/processing SINGULARITY_CACHEDIR=/data/EBC/processing singularity build /data/EBC/processing/singularity_images/fmriprep-24.0.0.simg docker://nipreps/fmriprep:24.0.0
#
################################################################################

# usage documentation - shown if no text file is provided or if script is run outside EBC directory
Usage() {
	echo
	echo
	echo "Usage:"
	echo "./run_fmriprep.sh <config file> <list of subjects>"
	echo
	echo "Example:"
	echo "./run_fmriprep.sh config-pixar_mind-body.tsv TEBC-5y_subjs.txt"
	echo
	echo "TEBC-5y_subjs.txt is a file containing the participants to run fMRIPrep on:"
	echo "8010"
	echo "8011"
	echo "..."
	echo
	echo
	echo "This script must be run within the /data/EBC/ directory on the server due to space requirements."
	echo "The script will terminiate if run outside of the /data/EBC/ directory."
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

if [ ! ${1##*.} == "tsv" ]
then
	echo
	echo "The configuration file was not found."
	echo "The script must be submitted with (1) a configuration file name and (2) a subject-run list as in the example below."
	echo
	echo "./run_fmriprep.sh config-pixar_mind-body.tsv TEBC-5y_subjs.txt"
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
	echo "./run_fmriprep.sh config-pixar_mind-body.tsv TEBC-5y_subjs.txt"
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
derivDir=$(awk -F'\t' '$1=="derivDir"{print $2}' "$config")

# extract preprocessing relevant values from config file
multiecho=$(awk -F'\t' '$1=="multiecho"{print $2}' "$config")

# strip extra formatting if present
sharedDir="${sharedDir%$'\r'}"
bidsDir="${bidsDir%$'\r'}"
derivDir="${derivDir%$'\r'}"
multiecho="${multiecho%$'\r'}"

# convert the singularity image to a sandbox if it doesn't already exist to avoid having to rebuild on each run
if [ ! -d ${singularityDir}/fmriprep_sandbox ]
then
	apptainer build --sandbox ${singularityDir}/fmriprep_sandbox ${singularityDir}/fmriprep-24.0.0.simg
fi

# export freesurfer license file location
export license=/data/EBC/local/infantFS/freesurfer/license.txt

# change the location of the singularity cache ($HOME/.singularity/cache by default, but limited space in this directory)
export APPTAINER_TMPDIR=${singularityDir}
export APPTAINER_CACHEDIR=${singularityDir}
unset PYTHONPATH

# prepare some writeable bind-mount points
export APPTAINERENV_TEMPLATEFLOW_HOME=${singularityDir}/fmriprep/.cache/templateflow

# display subjects
echo
echo "Running fMRIPrep for..."
echo "${subjs}"

# iterate for all subjects in the text file
while read p
do
	sub=` basename ${p} `

	echo
	echo "Running fMRIprep for sub-${sub}"
	echo
	
	# run fmriprep depending on whether data are multi-echo
	if [[ "${multiecho}" == "yes" ]]
	then
		echo "Data were aquired with a multi-echo sequence. Running multi-echo fMRIPrep command..."
		
		# run singularity
		apptainer run -C -B /data/EBC:/data/EBC,${singularityDir}:/opt/templateflow				\
		${singularityDir}/fmriprep_sandbox														\
		${bidsDir} ${derivDir}																	\
		participant																				\
		--participant-label ${sub}																\
		--skip_bids_validation																	\
		--nthreads 16																			\
		--omp-nthreads 16																		\
		--ignore slicetiming																	\
		--fd-spike-threshold 1																	\
		--dvars-spike-threshold 1.5																\
		--me-t2s-fit-method curvefit															\
		--me-output-echos																		\
		--output-space MNI152NLin2009cAsym:res-2 T1w											\
		--return-all-components																	\
		--derivatives ${derivDir}																\
		--stop-on-first-crash																	\
		-w ${singularityDir}																	\
		--fs-license-file ${license}  > ${derivDir}/sub-${sub}/log_fmriprep_sub-${sub}.txt
	# if data were not acquired with multiecho sequence
	else
		echo "Data were not acquired with a multi-echo sequence. Running default fMRIPrep command..."
		
		# run singularity
		apptainer run -C -B /data/EBC:/data/EBC,${singularityDir}:/opt/templateflow				\
		${singularityDir}/fmriprep_sandbox														\
		${bidsDir} ${derivDir}																	\
		participant																				\
		--participant-label ${sub}																\
		--skip_bids_validation																	\
		--nthreads 16																			\
		--omp-nthreads 16																		\
		--ignore slicetiming																	\
		--fd-spike-threshold 1																	\
		--dvars-spike-threshold 1.5																\
		--output-space MNI152NLin2009cAsym:res-2 T1w											\
		--return-all-components																	\
		--derivatives ${derivDir}																\
		--stop-on-first-crash																	\
		-w ${singularityDir}																	\
		--fs-license-file ${license}  > ${derivDir}/sub-${sub}/log_fmriprep_sub-${sub}.txt
	fi
	
	# move subject report and freesurfer output files to appropriate directories
	mv ${derivDir}/*dseg.tsv ${derivDir}/sourcedata/freesurfer
	mv ${derivDir}/sub-${sub}.html ${derivDir}/sub-${sub}
	
	# give other users permissions to created files
	#chmod -R a+wrx ${derivDir}/sub-${sub}

done <$2
