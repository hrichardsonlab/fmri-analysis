#!/bin/bash

################################################################################
# RUN FMRIPREP ON BIDS DATA
#
# The fMRIPrep singularity was installed using the following code:
# 	SINGULARITY_TMPDIR=/RichardsonLab/processing SINGULARITY_CACHEDIR=/RichardsonLab/processing sudo singularity build /RichardsonLab/processing/singularity_images/fmriprep-24.0.0.simg docker://nipreps/fmriprep:24.0.0 
#
################################################################################

# usage documentation
Usage() {
	echo
	echo
	echo "Usage:"
	echo "./run_fmriprep.sh <config file> <list of subjects>"
	echo
	echo "Example:"
	echo "./run_fmriprep.sh config-pixar_mind-body.tsv open-pixar_subjs.txt"
	echo
	echo "open-pixar_subjs.txt is a file containing the participants to run fMRIPrep on:"
	echo "sub-pixar001"
	echo "sub-pixar002"
	echo "..."
	echo
	echo
	echo "This script must be run within the /RichardsonLab/ directory on the server due to space requirements."
	echo "The script will terminiate if run outside of the /RichardsonLab/ directory."
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
	echo "./run_fmriprep.sh config-pixar_mind-body.tsv open-pixar_subjs.txt"
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
	echo "./run_fmriprep.sh config-pixar_mind-body.tsv open-pixar_subjs.txt"
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
task=$(awk -F'\t' '$1=="task"{print $2}' "$config")

# strip extra formatting if present
sharedDir="${sharedDir%$'\r'}"
bidsDir="${bidsDir%$'\r'}"
derivDir="${derivDir%$'\r'}"
multiecho="${multiecho%$'\r'}"
task="${task%$'\r'}"

# define project specific task directory
scratchDir=/Scratch/RichardsonLab/fmriprep/${task}

# export freesurfer license file location
export license=${sharedDir}/tools/license.txt

# create derivatives directory if it doesn't exist
if [ ! -d ${derivDir} ]
then 
	mkdir -p ${derivDir}
fi

if [ ! -d ${derivDir}/sourcedata ]
then 
	mkdir -p ${derivDir}/sourcedata/freesurfer
fi

if [ ! -d ${scratchDir} ]
then 
	mkdir -p ${scratchDir}
fi

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
	echo "Running fMRIprep for ${sub}"
	echo
	
	# make output subject derivatives directory
	mkdir -p ${scratchDir}/${sub}
	
	# run fmriprep depending on whether data are multi-echo
	if [[ "${multiecho}" == "yes" ]]
	then
		echo "Data were aquired with a multi-echo sequence. Running multi-echo fMRIPrep command..."
		
		# run singularity
		singularity run -B /RichardsonLab:/RichardsonLab,/Scratch:/Scratch,${singularityDir}:/opt/templateflow	\
		${singularityDir}/fmriprep-24.0.0.simg													\
		${bidsDir} ${scratchDir}																\
		participant																				\
		--participant-label ${sub}																\
		--skip_bids_validation																	\
		--nthreads 8																			\
		--omp-nthreads 4																		\
		--ignore slicetiming																	\
		--fd-spike-threshold 1																	\
		--dvars-spike-threshold 1.5																\
		--me-t2s-fit-method curvefit															\
		--me-output-echos																		\
		--output-space MNI152NLin2009cAsym:res-2 T1w											\
		--return-all-components																	\
		--derivatives ${scratchDir}																\
		--stop-on-first-crash																	\
		-w ${singularityDir}																	\
		--fs-license-file ${license}  > ${scratchDir}/${sub}/log_fmriprep_${sub}.txt
	# if data were not acquired with multiecho sequence
	else
		echo "Data were not acquired with a multi-echo sequence. Running default fMRIPrep command..."
		
		# run singularity
		singularity run -B /RichardsonLab:/RichardsonLab,/Scratch:/Scratch,${singularityDir}:/opt/templateflow	\
		${singularityDir}/fmriprep-24.0.0.simg													\
		${bidsDir} ${scratchDir}																\
		participant																				\
		--participant-label ${sub}																\
		--skip_bids_validation																	\
		--nthreads 8																			\
		--omp-nthreads 4																		\
		--ignore slicetiming																	\
		--fd-spike-threshold 1																	\
		--dvars-spike-threshold 1.5																\
		--output-space MNI152NLin2009cAsym:res-2 T1w											\
		--return-all-components																	\
		--derivatives ${scratchDir}																\
		--stop-on-first-crash																	\
		-w ${singularityDir}																	\
		--fs-license-file ${license}  > ${scratchDir}/${sub}/log_fmriprep_${sub}.txt
	fi
	
	# move freesurfer output files to appropriate directories
	mv ${scratchDir}/*dseg.tsv ${scratchDir}/sourcedata/freesurfer
	
	# move files from scratch directory to derivatives directory
	mv ${scratchDir}/${sub}.html ${derivDir}
	cp -r ${scratchDir}/${sub} ${derivDir}
	cp -r ${scratchDir}/logs ${derivDir}
	cp -r ${scratchDir}/sourcedata/freesurfer/fsaverage ${derivDir}/sourcedata/freesurfer
	cp -r ${scratchDir}/sourcedata/freesurfer/${sub} ${derivDir}/sourcedata/freesurfer
	
	# delete subject scratch directories
	rm -r ${scratchDir}/${sub}
	rm -r ${scratchDir}/sourcedata/freesurfer/${sub}
	
done <$2

#rm -r ${scratchDir}
