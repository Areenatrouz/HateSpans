import os
import shutil
import statistics

from sklearn.model_selection import train_test_split

from examples.english.transformer_configs import transformer_config, MODEL_TYPE, MODEL_NAME, LANGUAGE_FINETUNE, \
    language_modeling_args, TEMP_DIRECTORY
from hatespans.algo.evaluation import f1
from hatespans.algo.hate_spans_model import HateSpansModel
from hatespans.algo.language_modeling import LanguageModelingModel
from hatespans.algo.predict import predict_spans
from hatespans.algo.preprocess import read_datafile, format_data, format_lm, split_data
import torch
import numpy as np


if not os.path.exists(TEMP_DIRECTORY):
    os.makedirs(TEMP_DIRECTORY)

train = read_datafile('examples/english/data/tsd_train.csv')
dev = read_datafile('examples//english/data/tsd_trial.csv')


if LANGUAGE_FINETUNE:
    train_list = format_lm(train)
    dev_list = format_lm(dev)

    complete_list = train_list + dev_list
    lm_train = complete_list[0: int(len(complete_list)*0.8)]
    lm_test = complete_list[-int(len(complete_list)*0.2):]

    with open(os.path.join(TEMP_DIRECTORY, "lm_train.txt"), 'w') as f:
        for item in lm_train:
            f.write("%s\n" % item)

    with open(os.path.join(TEMP_DIRECTORY, "lm_test.txt"), 'w') as f:
        for item in lm_test:
            f.write("%s\n" % item)

    model = LanguageModelingModel("auto", MODEL_NAME, args=language_modeling_args, use_cuda=torch.cuda.is_available())
    model.train_model(os.path.join(TEMP_DIRECTORY, "lm_train.txt"), eval_file=os.path.join(TEMP_DIRECTORY, "lm_test.txt"))
    MODEL_NAME = language_modeling_args["best_model_dir"]

# model = HateSpansModel(MODEL_TYPE, MODEL_NAME, labels=tags, args=transformer_config)
dev_preds = np.empty((len(dev), transformer_config["n_fold"]))
for i in range(transformer_config["n_fold"]):
    if os.path.exists(transformer_config['output_dir']) and os.path.isdir(transformer_config['output_dir']):
        shutil.rmtree(transformer_config['output_dir'])
    print("Started Fold {}".format(i))

    if transformer_config["evaluate_during_training"]:
        train_list, val_list = split_data(train, seed=int(transformer_config["manual_seed"])*(i+1))
        train_df = format_data(train_list)
        val_df = format_data(train_list)
        tags = train_df['labels'].unique().tolist()
        model = HateSpansModel(MODEL_TYPE, MODEL_NAME, labels=tags, args=transformer_config)
        model.train_model(train_df, eval_df=val_df)
        model = HateSpansModel(MODEL_TYPE, transformer_config["best_model_dir"], labels=tags, args=transformer_config)

    else:
        train_df = format_data(train)
        tags = train_df['labels'].unique().tolist()
        model = HateSpansModel(MODEL_TYPE, MODEL_NAME, labels=tags, args=transformer_config)

    scores = []
    predictions_list = []
    for n, (spans, text) in enumerate(dev):
        predictions = predict_spans(model, text)
        predictions_list.append(predictions)
        score = f1(predictions, spans)
        scores.append(score)

    dev_preds[:, i] = predictions_list
    print('avg F1 %g' % statistics.mean(scores))

scores = []
for n, (spans, text) in enumerate(dev):
    majority_span = []
    fold_predictions = dev_preds[n]
    for index in range(0, len(text)):
        count = 0
        for fold_prediction in fold_predictions:
            if index in fold_prediction:
                count += 1
        if count/transformer_config["n_fold"] >= 0.5:
            majority_span.append(index)
    score = f1(majority_span, spans)
    scores.append(score)

print('avg F1 %g' % statistics.mean(scores))









