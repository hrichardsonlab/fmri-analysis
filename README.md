### fMRI pipeline
These folders have the scripts for running the fMRI analysis pipeline, written in python and bash:

* Converting from raw DICOMS to run-separated data in BIDS specification
* Data quality inspection using MRIQC
* Preprocessing using fMRIPrep
  * The data are optionally first run through the anatomical-only workflow using freesurfer within fMRIPrep because some participants only have structural data
  * The data are then run through the rest of the fMRIPrep workflow including:
	* Separating brain from skull, calculating brain tissue segmentation, spatial normalization
	* Confound estimation
  * Derivative data can be optionally run through tedana if multi-echo data were acquired
* Motion estimation for data exclusion
* First-level modeling
   * Contrast generation
   * Splithalf functionality (i.e., analyse full or half runs)
   * Adult ROI timecourse regression
   * Parametric modulation
   * Timecourse extraction
   * Combine runs
   * Extract stats
* Second-level modeling
  * Parametric and non-parametric group analysis
  * Reverse correlation
  * Cluster labeling
* Miscellaneous
  * Resample ROIs
  * Get outlier and run information
  * Interpolate timecourses
  * Compile subject timecourse files

See the Wiki page for more detailed information about running each step of the pipeline.
