"""
Takes the skimmed pickles (output of bbVVSkimmer) and trains a BDT using xgboost.

Author(s): Raghav Kansal
"""

import argparse
import os
from os.path import exists

import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_curve
import xgboost as xgb

import utils
import plotting

# import matplotlib.pyplot as plt


# import importlib
# importlib.reload(utils)
# importlib.reload(plotting)


# backgrounds listed first and plotted in order
keys = ["V", "Top", "QCD", "HHbbVV4q"]
labels = ["VV/V+jets", "ST/TT", "QCD", "HHbbVV4q"]
num_bg = 3  # up to this label for bg
sig = "HHbbVV4q"


bdtVars = [
    "MET_pt",
    "DijetEta",
    "DijetPt",
    "DijetMass",
    "bbFatJetPt",
    "VVFatJetEta",
    "VVFatJetPt",
    "VVFatJetMsd",
    "VVFatJetParticleNet_Th4q",
    "bbFatJetPtOverDijetPt",
    "VVFatJetPtOverDijetPt",
    "VVFatJetPtOverbbFatJetPt",
]


# Just for checking
# for key in keys:
#     print(f"{key} events: {np.sum(events[key]['finalWeight']):.2f}")
#
# TOT_BG_EVENTS = 34940902
# TOT_SIG_EVENTS = 2.6
# NUM_SIM_SIG_EVENTS = 223334

# sum([np.sum(events[key]['finalWeight']) for key in keys[:num_bg]])
# np.sum(events[sig]['finalWeight'])
# len(events[sig]['weight'])


def main(args):
    print("Setup")

    data_path = f'{args.data_dir}/{"all" if args.num_events <= 0 else args.num_events}_events_{"" if args.preselection else "no_"}preselection_{"equalized_weights_" if args.equalize_weights else ""}test_size_0{args.test_size * 10:.0f}_seed_{args.seed}'
    print(f"{data_path = }")

    classifier_params = {"max_depth": 3, "learning_rate": 0.1, "n_estimators": 400, "verbosity": 2, "n_jobs": 4, "reg_lambda": 1.0}

    if args.load_data and exists(data_path):
        X_full, X_train, X_test, X_Txbb_train, X_Txbb_test, y_train, y_test, weights_train, weights_test = load_training_data(data_path)
    else:
        os.system(f"mkdir -p {data_path}")
        events = load_events(args.pickles_dir, num_events=args.num_events, preselection=args.preselection, keys=utils.getAllKeys())
        X_train, X_test, X_Txbb_train, X_Txbb_test, y_train, y_test, weights_train, weights_test = preprocess_events(
            events, bdtVars, test_size=args.test_size, seed=args.seed, save=args.save_data, save_dir=data_path
        )
        X_full = preprocess_events(events, bdtVars, ret_X_only=True, keys=utils.getAllKeys(), save=args.save_data, save_dir=data_path)  # for inference
        del(events)

    if args.evaluate_only or args.inference_only:
        model = xgb.XGBClassifier()
        model.load_model(f"{args.model_dir}/trained_bdt.model")
    else:
        os.system(f"mkdir -p {args.model_dir}")
        model = train_model(
            X_train,
            X_test,
            y_train,
            y_test,
            weights_train,
            args.model_dir,
            use_sample_weights=args.use_sample_weights,
            early_stopping_rounds=args.early_stopping_rounds,
            **classifier_params,
        )

    if not args.inference_only:
        evaluate_model(model, args.model_dir, X_test, X_Txbb_test, y_test, weights_test)

    if not args.evaluate_only:
        do_inference(model, args.model_dir, X_full)


def load_events(pickles_path: str, num_events: int = 0, preselection: bool = True, keys: list = keys):
    """
    Loads events from pickles.
    If `num_events` > 0, only returns `num_events` entries for each sample.
    If `preselection` is True, applies a preselection as defined below
    """
    print("Loading events")
    import pickle

    events = {}
    for key in keys:
        # if key != sig: continue
        print(key)
        with open(f"{pickles_path}/{key}.pkl", "rb") as file:
            events[key] = pickle.load(file)["skimmed_events"]

    if num_events > 0:
        for key in keys:
            for var in events[key].keys():
                events[key][var] = events[key][var][:num_events]

    if preselection:
        for key in keys:
            cut = (events[key]["bbFatJetParticleNetMD_Txbb"] > 0.8) * (events[key]["bbFatJetMsd"] > 50) * (events[key]["VVFatJetMsd"] > 50)
            for var in events[key].keys():
                events[key][var] = events[key][var][cut]

    # Just for checking
    for key in keys:
        print(f"{key} events: {np.sum(events[key]['finalWeight']):.2f}")

    return events


#
# events = load_events('../../data/2017_combined/', preselection=False)
#
# bdt_presel_cut = {}
#
# for key in keys:
#     bdt_presel_cut[key] = (events[key]['bbFatJetPt'] > 250) * (events[key]['VVFatJetPt'] > 250) * (events[key]['bbFatJetParticleNetMD_Txbb'] > 0.8) * (events[key]['bbFatJetMsd'] > 50) * (events[key]['VVFatJetMsd'] > 50)
#
# # Just for checking
# print("Post bdt preselection")
# for key in keys:
#     print(f"{key} events: {np.sum(events[key]['finalWeight'][bdt_presel_cut[key]]):.2f}")
#
#
# import pickle
# from coffea.lookup_tools.dense_lookup import dense_lookup
#
# with open('../corrections/trigEffs/AK8JetHTTriggerEfficiency_2017.hist', 'rb') as filehandler:
#     ak8TrigEffs = pickle.load(filehandler)
#
# ak8TrigEffsLookup = dense_lookup(np.nan_to_num(ak8TrigEffs.view(flow=False), 0), np.squeeze(ak8TrigEffs.axes.edges))
#
# for key in keys:
#     if key == 'Data':
#         events[key]['finalWeight'] = events[key]['weight']
#     else:
#         fj1_trigEffs = ak8TrigEffsLookup(events[key]['ak8FatJetPt'][:, 0], events[key]['ak8FatJetMsd'][:, 0])
#         fj2_trigEffs = ak8TrigEffsLookup(events[key]['ak8FatJetPt'][:, 1], events[key]['ak8FatJetMsd'][:, 1])
#         combined_trigEffs = 1 - (1 - fj1_trigEffs) * (1 - fj2_trigEffs)
#         events[key]['final4bWeight'] = events[key]['weight'] * combined_trigEffs
#
# with open('../../data/2017_combined/data.pkl', 'rb') as file:
#     data = pickle.load(file)['skimmed_events']
#
# events['Data'] = data
#
# QCD_SCALE_FACTOR =  (np.sum(data['weight']) - np.sum(events['Top']['final4bWeight']) - np.sum(events['V']['final4bWeight'])) / (np.sum(events['QCD']['final4bWeight']))
# events['QCD']['final4bWeight'] *= QCD_SCALE_FACTOR
#
# for key in keys:
#     print(f"Final {key} events: {np.sum(events[key]['final4bWeight']):.2f}")
#
# # For checking against 4b AN
# bbbb_presel_cut = {}
#
# for key in keys:
#     bbbb_presel_cut[key] = (events[key]['ak8FatJetPt'][:, 0] > 300) * (events[key]['ak8FatJetPt'][:, 1] > 300) * (events[key]['ak8FatJetMsd'][:, 0] > 50) * (events[key]['ak8FatJetMsd'][:, 1] > 50) * (events[key]['ak8FatJetParticleNetMD_Txbb'][:, 0] > 0.8)
#
# print("Post 4b preselection")
# for key in keys:
#     print(f"{key} events: {np.sum(events[key]['final4bWeight'][bbbb_presel_cut[key]]):.2f}")
#
#
# # For checking against 4b AN
# bbbb_presel_mass_cut = {}
#
# for key in keys:
#     bbbb_presel_mass_cut[key] =  (
#                                 (events[key]['ak8FatJetPt'][:, 0] > 300) *
#                                 (events[key]['ak8FatJetPt'][:, 1] > 300) *
#                                 (events[key]['ak8FatJetMsd'][:, 0] > 50) *
#                                 (events[key]['ak8FatJetMsd'][:, 1] > 110) *
#                                 (events[key]['ak8FatJetMsd'][:, 1] < 140) *
#                                 (events[key]['ak8FatJetParticleNetMD_Txbb'][:, 0] > 0.8)
#                             )
#
# print("Post 4b preselection")
# for key in keys:
#     if key == 'Data': print(f"{key} events: {np.sum(events[key]['weight'][bbbb_presel_mass_cut[key]]):.2f}")
#     else: print(f"{key} events: {np.sum(events[key]['final4bWeight'][bbbb_presel_mass_cut[key]]):.2f}")
#
#
# cut_based_sel = {}
#
# for key in keys:
#     cut_based_sel[key] =   (
#                                 (events[key]['bbFatJetPt'] > 250) *
#                                 (events[key]['VVFatJetPt'] > 250) *
#                                 (events[key]['bbFatJetParticleNetMD_Txbb'] > 0.95) *
#                                 (events[key]['VVFatJetParticleNet_Th4q'] > 0.95) *
#                                 (50 < events[key]['bbFatJetMsd']) *
#                                 # (100 < events[key]['bbFatJetMsd']) *
#                                 # (events[key]['bbFatJetMsd'] < 150) *
#                                 (110 < events[key]['VVFatJetMsd']) *
#                                 (events[key]['VVFatJetMsd'] < 150)
#                             )
#
# keys = ['V', 'Top', 'QCD', 'Data', 'HHbbVV4q']
#
# # Just for checking
# print("Post cut based sel")
# for key in keys:
#     print(f"{key} events: {np.sum(events[key]['finalWeight'][cut_based_sel[key]]):.2f}")
#
#
# preselection_mass = {}
#
# for key in keys:
#     preselection_mass[key] =   (
#                                 # (events[key]['bbFatJetPt'] > 250) *
#                                 # (events[key]['VVFatJetPt'] > 250) *
#                                 (events[key]['bbFatJetParticleNetMD_Txbb'] > 0.8) *
#                                 # (events[key]['VVFatJetParticleNet_Th4q'] > 0.95) *
#                                 # (50 < events[key]['bbFatJetMsd']) *
#                                 (100 < events[key]['bbFatJetMsd']) *
#                                 (events[key]['bbFatJetMsd'] < 150) *
#                                 (50 < events[key]['VVFatJetMsd'])
#                                 # (events[key]['VVFatJetMsd'] < 150)
#                             )
#
# # Just for checking
# print("Post cut based sel")
# for key in keys:
#     print(f"{key} events: {np.sum(events[key]['finalWeight'][preselection_mass[key]]):.2f}")
#
#
# events.keys()
#


def preprocess_events(
    events: dict,
    bdtVars: list,
    test_size: float = 0.3,
    seed: int = 4,
    save: bool = True,
    save_dir: str = "",
    equalize_weights: bool = False,
    keys: list = keys,
    ret_X_only: bool = False,
):
    """Preprocess events for training"""
    print("Preprocessing events")

    X = np.concatenate([np.concatenate([events[key][var][:, np.newaxis] for var in bdtVars], axis=1) for key in keys], axis=0)
    if ret_X_only:
        if save:
            np.save(f"{save_dir}/X_full.npy", X)
        return X
    X_Txbb = np.concatenate([events[key]["bbFatJetParticleNetMD_Txbb"] for key in keys])  # for the final ROC curve
    Y = np.concatenate((np.concatenate([np.zeros_like(events[key]["weight"][:]) for key in keys[:num_bg]]), np.ones_like(events[sig]["weight"][:])))
    weights = np.concatenate([events[key]["finalWeight"][:] for key in keys])

    if equalize_weights:
        tot_bg_events = sum([np.sum(events[key]["finalWeight"]) for key in keys[:num_bg]])
        tot_sig_events = np.sum(events[sig]["finalWeight"])
        bg_over_sig = tot_bg_events / tot_sig_events
        weights = np.concatenate([np.concatenate([events[key]["finalWeight"] for key in keys[:num_bg]]), events[sig]["finalWeight"] * bg_over_sig])
    else:
        weights = np.concatenate([events[key]["finalWeight"][:] for key in keys])

    X_train, X_test, X_Txbb_train, X_Txbb_test, y_train, y_test, weights_train, weights_test = train_test_split(
        X, X_Txbb, Y, weights, test_size=test_size, random_state=seed
    )

    if save:
        np.save(f"{save_dir}/X_train.npy", X_train)
        np.save(f"{save_dir}/X_test.npy", X_test)
        np.save(f"{save_dir}/X_Txbb_train.npy", X_Txbb_train)
        np.save(f"{save_dir}/X_Txbb_test.npy", X_Txbb_test)
        np.save(f"{save_dir}/y_train.npy", y_train)
        np.save(f"{save_dir}/y_test.npy", y_test)
        np.save(f"{save_dir}/weights_train.npy", weights_train)
        np.save(f"{save_dir}/weights_test.npy", weights_test)

    return X_train, X_test, X_Txbb_train, X_Txbb_test, y_train, y_test, weights_train, weights_test


def load_training_data(data_path: str):
    """Load pre-processed data directly if already saved"""
    print("Loading preprocessed training data")
    X_full = np.load(f"{data_path}/X_full.npy")
    X_train = np.load(f"{data_path}/X_train.npy")
    X_test = np.load(f"{data_path}/X_test.npy")
    X_Txbb_train = np.load(f"{data_path}/X_Txbb_train.npy")
    X_Txbb_test = np.load(f"{data_path}/X_Txbb_test.npy")
    y_train = np.load(f"{data_path}/y_train.npy")
    y_test = np.load(f"{data_path}/y_test.npy")
    weights_train = np.load(f"{data_path}/weights_train.npy")
    weights_test = np.load(f"{data_path}/weights_test.npy")
    return X_full, X_train, X_test, X_Txbb_train, X_Txbb_test, y_train, y_test, weights_train, weights_test


def train_model(
    X_train: np.array,
    X_test: np.array,
    y_train: np.array,
    y_test: np.array,
    weights_train: np.array,
    model_dir: str,
    use_sample_weights: bool = False,
    early_stopping_rounds: int = 5,
    **classifier_params,
):
    """Trains BDT. `classifier_params` are hyperparameters for the classifier"""
    print("Training model")
    model = xgb.XGBClassifier(**classifier_params)
    trained_model = model.fit(
        X_train, y_train, early_stopping_rounds=5, eval_set=[(X_test, y_test)], sample_weight=weights_train if use_sample_weights else None
    )
    trained_model.save_model(f"{model_dir}/trained_bdt.model")
    return model


def evaluate_model(
    model: xgb.XGBClassifier,
    model_dir: str,
    X_test: np.array,
    X_Txbb_test: np.array,
    y_test: np.array,
    weights_test: np.array,
    txbb_threshold: float = 0.98,
):
    """ """
    print("Evaluating model")
    preds = model.predict_proba(X_test)

    # sorting by importance
    feature_importance = np.array(list(zip(bdtVars, model.feature_importances_)))[np.argsort(model.feature_importances_)[::-1]]
    # np.savetxt(f"{model_dir}/feature_importance.txt", feature_importance)

    print("Feature importance")
    for feature, imp in feature_importance:
        print(f"{feature}: {imp}")

    fpr, tpr, thresholds = roc_curve(y_test, preds[:, 1], sample_weight=weights_test)
    plotting.rocCurve(fpr, tpr, title="ROC Curve", plotdir=model_dir, name="bdtroccurve")

    np.savetxt(f"{model_dir}/fpr.txt", fpr)
    np.savetxt(f"{model_dir}/tpr.txt", tpr)
    np.savetxt(f"{model_dir}/thresholds.txt", thresholds)

    if txbb_threshold:
        preds_txbb_threshold = preds[:, 1].copy()
        preds_txbb_threshold[X_Txbb_test < txbb_threshold] = 0

        fpr_txbb_threshold, tpr_txbb_threshold, thresholds_txbb_threshold = roc_curve(y_test, preds_txbb_threshold, sample_weight=weights_test)

        fpr_txbb_threshold[np.argmin(np.abs(tpr_txbb_threshold - 0.15))]
        thresholds_txbb_threshold[np.argmin(np.abs(tpr_txbb_threshold - 0.15))]

        plotting.rocCurve(
            fpr_txbb_threshold,
            tpr_txbb_threshold,
            title=f"ROC Curve Including Txbb {txbb_threshold} Cut",
            plotdir=model_dir,
            name="bdtroccurve_txbb_cut",
        )

        np.savetxt(f"{model_dir}/fpr_txbb_threshold.txt", fpr_txbb_threshold)
        np.savetxt(f"{model_dir}/tpr_txbb_threshold.txt", tpr_txbb_threshold)
        np.savetxt(f"{model_dir}/thresholds_txbb_threshold.txt", thresholds_txbb_threshold)


def do_inference(
    model: xgb.XGBClassifier,
    model_dir: str,
    X_full: np.array,
):
    """ """
    print("Running inference")
    preds = model.predict_proba(X_full)

    print(preds)
    print(preds.shape)

    np.save(f"{model_dir}/preds.npy", preds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--pickles-dir", default="/hhbbvvvol/data/2017_combined", help="event pickles directory", type=str)
    parser.add_argument(
        "--data-dir", default="/hhbbvvvol/data/2017_bdt_training", help="directory in which to save model and evaluation output", type=str
    )
    parser.add_argument("--model-dir", default="./", help="directory in which to save model and evaluation output", type=str)
    utils.add_bool_arg(parser, "load-data", "Load pre-processed data if done already", default=True)
    utils.add_bool_arg(parser, "save-data", "Save pre-processed data if loading the data", default=True)

    parser.add_argument("--num-events", default=0, help="Num events per sample to train on - if 0 train on all", type=int)
    utils.add_bool_arg(parser, "preselection", "Apply preselection on events before training", default=True)

    utils.add_bool_arg(parser, "use-sample-weights", "Use properly scaled event weights", default=False)
    utils.add_bool_arg(parser, "equalize-weights", "Equalise signal and background weights", default=False)

    parser.add_argument("--early-stopping-rounds", default=5, help="early stopping rounds", type=int)
    parser.add_argument("--test-size", default=0.3, help="testing/training split", type=float)
    parser.add_argument("--seed", default=4, help="seed for testing/training split", type=int)

    utils.add_bool_arg(parser, "evaluate-only", "Only evaluation, no training", default=False)
    utils.add_bool_arg(parser, "inference-only", "Only inference, no training", default=False)

    args = parser.parse_args()

    if args.equalize_weights:
        args.use_sample_weights = True  # sample weights are used before equalizing
    main(args)
