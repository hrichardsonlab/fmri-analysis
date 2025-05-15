"""
Runs reverse correlation analysis on timecourses extracted by running the timecourse_pipeline.py script

Returns:
csv and text files with averaged timecourses, t-stats, p-values, information on identified events

Parameters:
mask - masks to conduct reverse correlation analysis within, timecourses should already have been extracted
hrf_lag - to account for lag in HRF between timing of the presentation of movie content and identified events
rc_thresh - p-value threshold to apply to each timepoint to identify moment significantly different from 0
rc_ntps - number of consecutive timepoints that need to exceed threshold in order to be tagged as a event

"""
import os
import os.path as op
import glob
import numpy as np
import pandas as pd
import argparse
from scipy.stats import ttest_1samp
from bids.layout import BIDSLayout

# define timecourse processing function
def process_timecourses(resultsDir, outDir, subjects, runs, task, TR, mask_id, splithalf_id, hrf_lag, rc_ntps, rc_thresh):
    # initialize output
    sub_timecourses = pd.DataFrame()
    
    # select subject timecourse files
    for s, sub in enumerate(subjects):
        # process subject run info
        sub_runs=runs[s]
        sub_runs=sub_runs.replace(' ','').split(',') # split runs by separators
        
        # grab all run files requested (typically this should only be 1, but possibly averaging across multiple runs is requested)
        for run in sub_runs:
            # define file name based on whether run info is present
            if run == 'NA':
                prefix = op.join(resultsDir, 'sub-{}'.format(sub), 'timecourses', 'sub-{}_task-{}*'.format(sub, task))
            else:
                prefix = op.join(resultsDir, 'sub-{}'.format(sub), 'timecourses', 'sub-{}_task-{}_run-{:02d}'.format(sub, task, int(run)))
            
            # define file name based on whether splithalf info is present
            if splithalf_id != 0:
                prefix = prefix + '_splithalf-{:02d}_{}*'.format(splithalf_id, mask_id)
            else:
                prefix = prefix + '_{}*'.format(mask_id)
            
            # check that file exists and warn if not         
            if glob.glob(prefix):
                sub_file = glob.glob(prefix)[0]
                print('Will use {}'.format(sub_file))
            else:
                print('Timecourse file for {} for sub-{} not found'.format(mask_id, sub))
                continue
            
            # read in file and append timecourse column to dataframe
            sub_tc = pd.read_csv(sub_file, header=None)
            sub_timecourses['{}'.format(sub)] = sub_tc[0]
    
    # calculate average timecourse
    avg_tc = sub_timecourses.mean(axis=1)
    
    # create vectors capturing volume/TR number and convert to raw and shifted time stamps
    vol_nums = np.arange(1, len(avg_tc)+1)
    raw_time = vol_nums * TR
    shifted_time = raw_time - hrf_lag
    
    # do t-test to identify events
    t_stats, p_vals = ttest_1samp(sub_timecourses, popmean=0, nan_policy='omit', axis=1)
    
    # flag events exceeding p-value and number of timepoints thresholds
    events, event_type, event_mean, event_magnitude, event_duration, event_rank = identify_events(p_vals, avg_tc, rc_thresh, rc_ntps, TR)

    # store results in dataframe
    results = pd.DataFrame({'vol_num': vol_nums,
                            'raw_time': raw_time,
                            'shifted_time': shifted_time,
                            'ROI': mask_id,
                            'avg_tc': avg_tc,
                            't_stat': t_stats,
                            'p_val': p_vals,
                            'event': events,
                            'type': event_type,
                            'event_mean': event_mean,
                            'event_magnitude': event_magnitude,
                            'event_duration': event_duration,
                            'event_rank': event_rank})
    
    # save results
    results_file = op.join(outDir, '{}_thresh-{}_lag-{}_ntps-{}.csv'.format(mask_id, rc_thresh, hrf_lag, rc_ntps))
    print('Saving results to file: {}'.format(results_file))
    results.to_csv(results_file, index=False)
    
    # generate and save summary text file
    # extract only events
    summary_df = results[results['event'] == 'yes']
    if len(summary_df) != 0:
        summary_df = summary_df.drop_duplicates(subset=['event_rank'])
        summary_file = op.join(outDir, 'events_{}.tsv'.format(mask_id))
        summary_df.to_csv(summary_file, index=False, sep='\t')
    else:
        print('Summary events file will not be saved for {} because no events identified'.format(mask_id))
    
# define event identification function
def identify_events(p_vals, avg_tc, rc_thresh, rc_ntps, TR):
    # identify timepoints below specified significance threshold
    sig_tps = p_vals <= rc_thresh
    
    # initialize output variables to match length of data
    events = ['no'] * len(p_vals)
    event_mean = [np.nan] * len(avg_tc)
    event_mag = [np.nan] * len(avg_tc)
    event_dur = [np.nan] * len(avg_tc)
    event_type = [np.nan] * len(avg_tc)
    
    # iterate through significant timepoints
    start = None # marks the start of a event
    
    # flag events as those that are below significance threshold and occur over across specified number of timepoints
    for t, sig in enumerate(sig_tps):
        # when value is TRUE (i.e., significant timepoint)
        if sig:
            if start is None:
                start = t  # reset event start
        # when value is FALSE (i.e., nonsignificant timepoint
        else:
            # if we were in an identified event (i.e., start isn't None)
            if start is not None:
                # check if event was longer than specified number of timepoints
                if t - start >= rc_ntps:
                    # if longer than specified number of timepoints, mark all event timepoints as 'yes'
                    for j in range(start, t):
                        # calculate event mean signal and duration
                        event_mean[j] = avg_tc[start:t].mean()
                        max_idx = (avg_tc[start:t].abs()).idxmax() 
                        event_mag[j] = avg_tc[max_idx]
                        event_dur[j] = (t - start) * TR
                        events[j] = 'yes'
                        # tag as a peak or valley event based on mean value
                        if event_mean[j] < 0:
                            event_type[j] = 'valley'
                        else:
                            event_type[j] = 'peak'
                        
                start = None  # reset event start because event is over
                
    # if the timecourse ends with a event
    if start is not None and len(sig_tps) - start >= rc_ntps:
        for j in range(start, len(sig_tps)):
            # calculate event mean signal and duration
            event_mean[j] = avg_tc[start:t].mean()
            max_idx = (avg_tc[start:t].abs()).idxmax() 
            event_mag[j] = avg_tc[max_idx]
            event_dur[j] = (len(sig_tps) - start) * TR
            events[j] = 'yes'    
            # tag as a peak or valley event based on mean value
            if event_mean[j] < 0:
                event_type[j] = 'valley'
            else:
                event_type[j] = 'peak'
    
    # rank events according to magnitude
    valid_events = pd.DataFrame(event_mag)[0].dropna().unique()
    ranked_events = np.argsort(np.abs(valid_events))[::-1] + 1 # descending order
    
    # map event magnitudes to ranks
    rank_dict = dict(zip(valid_events, ranked_events))
    
    # apply ranks to event magnitude
    event_rank = [rank_dict.get(event, np.nan) for event in event_mag]
    
    print('{} events identified'.format(len(valid_events)))
    
    return events, event_type, event_mean, event_mag, event_dur, event_rank

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
    bidsDir=config_file.loc['bidsDir',1]
    resultsDir=config_file.loc['resultsDir',1]
    task=config_file.loc['task',1]
    splithalf=config_file.loc['splithalf',1]
    mask_opts=config_file.loc['mask',1].replace(' ','').split(',')
    hrf_lag=int(config_file.loc['hrf_lag',1])
    rc_ntps=int(config_file.loc['rc_ntps',1])
    rc_thresh=float(config_file.loc['rc_thresh',1])
    
    # print if BIDS directory is not found
    if not op.exists(bidsDir):
        raise IOError('BIDS directory {} not found.'.format(bidsDir))
        
    # print if the project directory is not found
    if not op.exists(resultsDir):
        raise IOError('Results directory {} not found.'.format(resultsDir))
    
    # make output and working directories
    outDir = op.join(resultsDir, 'group_analysis', 'reverse_correlation')
    os.makedirs(outDir, exist_ok=True)
    
    # if split half requested
    if splithalf == 'yes':
        splithalves=[1,2]
    else:
        splithalves=[0]
    
    # get layout of BIDS directory
    # this is necessary because the pipeline reads the functional json files that have TR info
    # the derivDir (where fMRIPrep outputs are) doesn't have json files with this information, so getting the layout of that directory will result in an error
    layout = BIDSLayout(bidsDir)
    
    # extract TR info from bidsDIR bold json files (assumes TR is same across runs)
    epi = layout.get(subject=args.subjects[0], suffix='bold', task=task, return_type='file')[0] # take first file
    TR = layout.get_metadata(epi)['RepetitionTime'] # extract TR field
    
    # check that run info was provided in subject list, otherwise throw an error
    if not args.runs:
        raise IOError('Run information missing. Make sure you are passing a subject-run list to the pipeline!')
    
    # for each mask/ROI
    for m, mask_id in enumerate(mask_opts):
        for s, splithalf_id in enumerate(splithalves):
            # redefine output directory if splithalf was requested
            if splithalf_id != 0:
                outDir = op.join(outDir, 'splithalf-{:02d}'.format(splithalf_id))
                os.makedirs(outDir, exist_ok=True)
                
            # pass inputs to timecourse processing function
            process_timecourses(resultsDir, outDir, args.subjects, args.runs, task, TR, mask_id, splithalf_id, hrf_lag, rc_ntps, rc_thresh)

# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()