#!/usr/bin/python

import json
import uproot
from coffea.nanoevents import NanoEventsFactory, NanoAODSchema, BaseSchema
from coffea import processor
import pickle

import argparse
import warnings


def get_fileset(ptype):
    if ptype == 'trigger':
        with open('data/SingleMuon_2017.txt', 'r') as file:
            filelist = [f[:-1] for f in file.readlines()]

        files = {'2017': filelist}
        fileset = {k: files[k][args.starti:args.endi] for k in files.keys()}
        return fileset

    elif ptype == 'skimmer':
        from os import listdir

        # TODO: replace with UL sample once we have it
        with open('data/2017_preUL_nano/HHToBBVVToBBQQQQ_cHHH1.txt', 'r') as file:
            filelist = [f[:-1].replace('/eos/uscms/', 'root://cmsxrootd.fnal.gov//') for f in file.readlines()]   # need to use xcache redirector at Nebraksa coffea-casa

        fileset = {
            '2017_HHToBBVVToBBQQQQ_cHHH1': filelist
        }

        # extra samples in the folder we don't need for this analysis - TODO: should instead have a list of all samples we need
        ignore_samples = ['GluGluHToTauTau_M125_TuneCP5_13TeV-powheg-pythia8',
                          'GluGluHToWWToLNuQQ_M125_TuneCP5_PSweight_13TeV-powheg2-jhugen727-pythia8',
                          'ST_tW_antitop_5f_DS_NoFullyHadronicDecays_TuneCP5_13TeV-powheg-pythia8',
                          'ST_tW_top_5f_DS_NoFullyHadronicDecays_TuneCP5_13TeV-powheg-pythia8']

        for sample in listdir('data/2017_UL_nano/'):
            if sample[-4:] == '.txt' and sample[:-4] not in ignore_samples:
                with open(f'data/2017_UL_nano/{sample}', 'r') as file:
                    if 'JetHT' in sample: filelist = [f[:-1].replace('/hadoop/cms/', 'root://redirector.t2.ucsd.edu//') for f in file.readlines()]
                    else: filelist = [f[:-1].replace('/eos/uscms/', 'root://cmsxrootd.fnal.gov//') for f in file.readlines()]

                fileset['2017_' + sample[:-4].split('_TuneCP5')[0]] = filelist


def main(args):

    # define processor
    if args.processor == "trigger":
        from processors import JetHTTriggerEfficienciesProcessor
        p = JetHTTriggerEfficienciesProcessor()
    elif args.processor == 'skimmer':
        from processors import bbVVSkimmer
        p = bbVVSkimmer(condor=args.condor)
    else:
        warnings.warn('Warning: no processor declared')
        return

    fileset = get_fileset(args.processor)

    if args.condor:
        uproot.open.defaults['xrootd_handler'] = uproot.source.xrootd.MultithreadedXRootDSource

        exe_args = {'savemetrics': True,
                    # 'schema': BaseSchema,
                    'schema': NanoAODSchema,
                    'retries': 1}

        out, metrics = processor.run_uproot_job(
            fileset,
            treename='Events',
            processor_instance=p,
            executor=processor.futures_executor,
            executor_args=exe_args,
            chunksize=10000,
    #        maxchunks=1
        )

        filehandler = open(f'outfiles/{args.year}_{args.starti}-{args.endi}.hist', 'wb')
        pickle.dump(out, filehandler)
        filehandler.close()

    elif args.dask:
        import time
        from distributed import Client
        from lpcjobqueue import LPCCondorCluster

        tic = time.time()
        cluster = LPCCondorCluster(
            # ship_env=True,
            # transfer_input_files="HHbbVV",
        )
        cluster.adapt(minimum=1, maximum=30)
        client = Client(cluster)

        exe_args = {
            'client': client,
            'savemetrics': True,
            'schema': BaseSchema,  # for base schema
            # 'schema': nanoevents.NanoAODSchema, # for nano schema in the future
            'align_clusters': True,
        }

        print("Waiting for at least one worker...")
        client.wait_for_workers(1)

        out, metrics = processor.run_uproot_job(
            fileset,
            treename="Events",
            processor_instance=p,
            executor=processor.dask_executor,
            executor_args=exe_args,
            #    maxchunks=10
        )

        elapsed = time.time() - tic
        print(f"Metrics: {metrics}")
        print(f"Finished in {elapsed:.1f}s")

        filehandler = open('out.hist', 'wb')
        pickle.dump(out, filehandler)
        filehandler.close()


if __name__ == "__main__":
    # e.g.
    # inside a condor job: python run.py --year 2017 --processor trigger --condor --starti 0 --endi 1
    # inside a dask job:  python run.py --year 2017 --processor trigger --dask

    parser = argparse.ArgumentParser()
    parser.add_argument('--year',       dest='year',       default='2017',       help="year", type=str)
    parser.add_argument('--starti',     dest='starti',     default=0,            help="start index of files", type=int)
    parser.add_argument('--endi',       dest='endi',       default=-1,           help="end index of files", type=int)
    parser.add_argument('--outdir',     dest='outdir',     default='outfiles',   help="directory for output files", type=str)
    parser.add_argument("--processor",  dest="processor",  default="trigger",    help="Trigger processor", type=str)
    parser.add_argument("--dask",       dest="dask",       action="store_true",  default=False, help="Run with dask")
    parser.add_argument("--condor",     dest="condor",     action="store_true",  default=True,  help="Run with condor")
    parser.add_argument('--samples',    dest='samples',    default=[],           help='samples',     nargs='*')
    args = parser.parse_args()

    main(args)
