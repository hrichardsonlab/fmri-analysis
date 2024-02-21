### fMRI pipeline
These folders have the scripts for running the fMRI analysis pipeline, written in python and bash:

* Converting from raw DICOMS to run-separated data in BIDS specification
* Preprocessing using fMRIPrep
  * The data are first run through the anatomical-only workflow using freesurfer within fMRIPrep because some participants only have structural data
  * The data are then run through the rest of the fMRIPrep workflow including:
	* Separating brain from skull, calculating brain tissue segmentation, spatial normalization
	* Confound estimation
* Motion estimation for data exclusion
* First-level modeling
* Subject-level modeling
* Group-level modeling


