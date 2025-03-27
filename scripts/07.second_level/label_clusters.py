"""
Find peak clusters in a stats map and label them using multiple atlases

Parameters:
stat_img: Statistical map (e.g., from a second-level analysis)
atlases: Dictionary with atlas names as keys and atlas file paths as values
threshold: Optional threshold for the statistical map
cluster_size: Minimum cluster size in voxels

Returns:
peak_clusters: List of peak coordinates and labels for each atlas

"""
import os
import os.path as op
import re
import glob
import argparse
import numpy as np
import pandas as pd
import nibabel as nib
from collections import Counter
from nilearn import image, plotting, reporting
from scipy.ndimage import label, center_of_mass
from nilearn.plotting import find_xyz_cut_coords
from nilearn.datasets import fetch_atlas_harvard_oxford, fetch_atlas_aal, fetch_atlas_schaefer_2018, fetch_atlas_yeo_2011

# define function to label clusters
def label_clusters(resultsDir, task, splithalf_id, contrast_id, nonparametric, tfce, thresh, cluster_size, top_nregions, atlases):
    
    # define output directory for this contrast depending on config options
    if nonparametric == 'yes':
        method = 'randomise'
    else:
        method = 'flame'
        
    if splithalf_id != 0:
        conDir = op.join(resultsDir, '{}_{}_{}_splithalf{}'.format(method, task, contrast_id, splithalf_id))
    else:
        conDir = op.join(resultsDir, '{}_{}_{}'.format(method, task, contrast_id))
        
    # redefine prefix to grab correct output file
    if tfce == 'yes':
        prefix = '{}_tfce_corrp'.format(method)
    else:
        prefix = ''.format(method)
    
    # grab stats maps
    stats_maps = glob.glob(op.join(conDir, '{}_tstat*'.format(prefix)))
    
    # remove stats maps that are already clustered (i.e., have suffixes after tstat#
    pattern = re.compile(rf"{re.escape(prefix)}_tstat\d+\.nii\.gz$")
    stats_maps = [s for s in stats_maps if pattern.search(op.basename(s))]
    
    # process each stat map separately
    for m, stat in enumerate(stats_maps):
        print('Labeling clusters found in {}'.format(stat))
        
        # extract informative part of the stat filename
        filename = os.path.basename(stat)
        contrast = re.findall(r'tstat\d+', filename)[0]
        
        # load stats map
        stat_img = nib.load(stat)
        stat_data = stat_img.get_fdata()
        
        # threshold the stats map and save cluster mask
        cluster_mask, cluster_labels, cluster_sizes = threshold_clusters(stat_img, thresh, cluster_size)
        
        # skip cluster labeling if no clusters returned
        if np.max(cluster_mask) == 0:
            print('No clusters survived thresholding. Skipping...')
            continue
        
        # apply cluster masks to tstats data if TFCE was used
        if tfce == 'yes':
            print('Will threshold t-stats map based on TFCE clusters')
            tstats_img = nib.load(glob.glob(op.join(conDir, '*e_{}.nii.gz'.format(contrast)))[0])
            tstats_data = tstats_img.get_fdata()
            
            # overwrite stats data to now be the t-values to identify peak voxels
            stat_data = np.zeros_like(tstats_data)
            stat_data[cluster_mask > 0] = tstats_data[cluster_mask > 0]
            
            # save file
            stat_img = nib.Nifti1Image(stat_data, tstats_img.affine, tstats_img.header)
            stat_file = op.join(conDir, '{}_{}_{}.nii.gz'.format(method, contrast, thresh))
            stat_img.to_filename(stat_file)
        
        # save clustered file
        cluster_img = nib.Nifti1Image(cluster_mask, stat_img.affine, stat_img.header)
        cluster_file = op.join(conDir, '{}_{}_{}_clustered.nii.gz'.format(prefix, contrast, thresh))
        cluster_img.to_filename(cluster_file)
        
        # initialize variable for storing peak coordinates and labels from each atlas
        cluster_info = []
            
        # loop through atlases
        for atlas_name, atlas in atlases.items():
            print('Looking up coordinates in {} atlas'.format(atlas_name))
            
            # load atlas and atlas labels, depending on whether labels need to be converted to dict (for local atlases)
            atlas_img = atlas['maps'] if isinstance(atlas['maps'], nib.Nifti1Image) else nib.load(atlas['maps'])
            
            if atlas_name == 'AAL' or atlas_name == 'Brainnectome':
                atlas_labels = {}
                
                with open(atlas['labels'], 'r') as file:
                    for line in file:
                        # split columns into keys and values
                        key, value = line.strip().split('\t')
                        atlas_labels[int(key)] = value
            else:
                atlas_labels = atlas['labels']
            
            # resample atlas to match clustered brain image
            atlas_img = image.resample_to_img(atlas_img, stat_img, interpolation='nearest')            
            
            # save resampled atlas file to conDir to check alignment if desired
            #atlas_file = op.join(conDir, '{}_{}_atlas.nii.gz'.format(prefix, atlas_name))
            #atlas_img.to_filename(atlas_file)
            
            # loop through clusters
            #for clust in np.unique(cluster_labels):
            for c, clust in enumerate(np.unique(cluster_labels)):
                if clust == 0: # skip background
                    continue
                    
                # grab cluster size
                clust_size = cluster_sizes[c]
                
                # isolate cluster
                clust_img = nib.Nifti1Image((cluster_mask == clust).astype(np.int32), stat_img.affine)
                
                # get center of mass coordinate and label regions
                center_indx = np.round(center_of_mass(cluster_mask == clust)).astype(int)
                center_coord = nib.affines.apply_affine(stat_img.affine, center_indx)
                center_label = label_coordinates(atlas_img, atlas_labels, center_coord)
                
                # get peak coordinate and label regions
                cluster_indx = np.argwhere(cluster_mask == clust)
                peak_indx = max(cluster_indx, key=lambda idx: stat_data[tuple(idx)])
                peak_coord = nib.affines.apply_affine(stat_img.affine, peak_indx)
                peak_label = label_coordinates(atlas_img, atlas_labels, peak_coord)
                        
                # mask atlas data to current cluster
                atlas_data = atlas_img.get_fdata()
                region_mask = atlas_data[cluster_mask == clust]
                
                # count occurrences of each atlas region in the cluster
                region_counts = Counter(region_mask)
                top_regions = [atlas_labels[int(region_id)] for region_id, _ in region_counts.most_common(top_nregions) if int(region_id) > 0]
                top_regions = '; '.join(top_regions)
                
                # store the cluster info
                cluster_info.append({'atlas': atlas_name,
                                     'cluster_number': clust,
                                     'cluster_size': clust_size,
                                     'peak_coordinate': peak_coord,
                                     'peak_label': peak_label,                                   
                                     'center_coordinate': center_coord,
                                     'center_label': center_label,
                                     'top_regions': top_regions})
        
        # save cluster info
        cluster_df = pd.DataFrame(cluster_info)
        df_file = op.join(conDir, '{}_{}_{}_clusters.csv'.format(prefix, contrast, thresh))
        cluster_df.to_csv(df_file, index=False)

# define cluster thresholding function
def threshold_clusters(stat_img, thresh, cluster_size):
    # load stats data
    data = stat_img.get_fdata()
    
    # threshold stats map
    if thresh == 0:
        print('Stats map will not be further thresholded')
    else:
        print('Thresholding stats map using {}'.format(thresh))
        data = np.where(data >= thresh, data, 0)
    
    # binarize the stats map
    print('Binarizing stats map')
    data_bin = (data > 0).astype(np.uint8)
    bin_img = nib.Nifti1Image(data_bin.astype(np.int32), stat_img.affine, dtype=np.int32)
    
    # isolate clusters (i.e., non-zero values)
    print('Isolating clusters')
    cluster_labels, nClusters = label(data_bin > 0)
    print('Found {} clusters'.format(nClusters))
    
    # create a mask to hold only valid clusters
    cluster_mask = np.zeros_like(data, dtype=np.int32)
    
    # filter clusters by size
    labels = []
    sizes = []
    for clust in np.unique(cluster_labels):
        if clust == 0: # skip background
            continue
        size = np.sum(cluster_labels == clust)
        if size >= cluster_size:
            cluster_mask[cluster_labels == clust] = clust
            
            # record cluster label and size
            labels.append(clust)
            sizes.append(size)
        
    return cluster_mask, labels, sizes
    
# define function to label coordinates
def label_coordinates(atlas_img, labels, coord):
    # load atlas data
    atlas_data = atlas_img.get_fdata()

    # transform peak coordinate to voxel index
    coord_indx = np.round(nib.affines.apply_affine(np.linalg.inv(atlas_img.affine), coord)).astype(int)

    # ensure the coordinate is in bounds
    if (0 <= coord_indx[0] < atlas_data.shape[0] and
        0 <= coord_indx[1] < atlas_data.shape[1] and
        0 <= coord_indx[2] < atlas_data.shape[2]):

        # retrieve atlas value at the voxel
        atlas_value = int(atlas_data[tuple(coord_indx)])

        # retrieve atlas label from the lookup table
        region_label = labels.get(atlas_value, f"Unknown ({atlas_value})")
    else:
        region_label = 'Location not found'
        
    return region_label
        
# define command line parser function
def argparser():
    # create an instance of ArgumentParser
    parser = argparse.ArgumentParser()
    # attach argument specifications to the parser
    parser.add_argument('-p', dest='projDir',
                        help='Project directory')
    parser.add_argument('-s', dest='subjects', nargs='*',
                        help='Subjects to process')
    parser.add_argument('-f', dest='file', nargs='*',
                        help='Subject file to process')  
    parser.add_argument('-r', dest='runs', nargs='*',
                        help='List of runs for each subject')                         
    parser.add_argument('-c', dest='config',
                        help='Configuration file')                                            
    parser.add_argument('-m', dest='plugin',
                        help='Nipype plugin to use (default: MultiProc)')
    return parser

# define main function that parses the config file and runs the functions defined above
def main(argv=None):
    # call argparser function that defines command line inputs
    parser = argparser()
    args = parser.parse_args(argv)   
        
    # print if the project directory is not found
    if not op.exists(args.projDir):
        raise IOError('Project directory {} not found.'.format(args.projDir))
    
    # print if config file is not found
    if not op.exists(args.config):
        raise IOError('Configuration file {} not found. Make sure it is saved in your project directory!'.format(args.config))
    
    # read in configuration file and parse inputs
    config_file=pd.read_csv(args.config, sep='\t', header=None, index_col=0).replace({np.nan: None})
    sharedDir=config_file.loc['sharedDir',1]
    resultsDir=config_file.loc['resultsDir',1]
    task=config_file.loc['task',1]
    contrast_opts=config_file.loc['contrast',1].replace(' ','').split(',')
    splithalf=config_file.loc['splithalf',1]
    nonparametric=config_file.loc['nonparametric',1]
    tfce=config_file.loc['tfce',1]
    thresh=float(config_file.loc['stat_thresh',1])
    cluster_size=float(config_file.loc['cluster_size',1])
    top_nregions=int(config_file.loc['top_nregions',1])
    overwrite=config_file.loc['overwrite',1]
        
    # print if the project directory is not found
    if not op.exists(resultsDir):
        raise IOError('Results directory {} not found.'.format(resultsDir))
    
    # lowercase contrast_opts and group_vars to avoid case errors
    contrast_opts = [c.lower() for c in contrast_opts]
    
    # if split half requested
    if splithalf == 'yes':
        splithalves=[1,2]
    else:
        splithalves=[0]
    
    # define atlas directory where shared atlases are saved and new atlases will be downloaded to
    atlasDir = op.join(sharedDir, 'atlases')
    
    # define atlases
    atlases = {'Harvard-Oxford': {'maps': fetch_atlas_harvard_oxford('cort-maxprob-thr0-1mm', data_dir=atlasDir)['maps'],
                                  'labels': dict(enumerate(fetch_atlas_harvard_oxford('cort-maxprob-thr0-1mm', data_dir=atlasDir)['labels']))},
               'Harvard-Oxford_subcortical': {'maps': fetch_atlas_harvard_oxford('sub-maxprob-thr0-1mm', data_dir=atlasDir)['maps'],
                                              'labels': dict(enumerate(fetch_atlas_harvard_oxford('sub-maxprob-thr0-1mm', data_dir=atlasDir)['labels']))},
               'AAL': {'maps': nib.load(op.join(atlasDir, 'AAL', 'aal.nii.gz')),
                       'labels': op.join(atlasDir, 'AAL', 'aal.nii.txt')},
               'Brainnectome': {'maps': nib.load(op.join(atlasDir, 'Brainnectome', 'Brainnectome.nii.gz')),
                                'labels': op.join(atlasDir, 'Brainnectome', 'Brainnectome.txt')}}
                                              
    # for each contrast
    for c, contrast_id in enumerate(contrast_opts):
        for s, splithalf_id in enumerate(splithalves):
            # pass inputs to label clusters function
            label_clusters(resultsDir, task, splithalf_id, contrast_id, nonparametric, tfce, thresh, cluster_size, top_nregions, atlases)

# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()