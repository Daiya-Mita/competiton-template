# import pandas as pd
import datetime
import logging
import argparse
import subprocess
import json
import random
import os
import sys
this_folder = '/user01'
cwd = os.getcwd()
sys.path.append(cwd.replace(this_folder, ''))
from models.kfold_lgbm import kfold_lightgbm, kfold_lightgbm_without_outliers
from models.kfold_xgb import kfold_xgb
from utils import load_datasets, removeMissingColumns, create_score_log, make_output_dir, save_importances, save2pkl, submit  # , line_notify, load_target


# config
create_features = False  # create_features.py を再実行する場合は True, そうでない場合は False
is_debug = False  # True だと少数のデータで動かします, False だと全データを使います. また folds = 2 になります
use_GPU = False
target_col = 'target'
feats_exclude = ['first_active_month', 'target', 'card_id', 'outliers',
                  'hist_purchase_date_max', 'hist_purchase_date_min', 'hist_card_id_size',
                  'new_purchase_date_max', 'new_purchase_date_min', 'new_card_id_size',
                  'Outlier_Likelyhood', 'OOF_PRED', 'outliers_pred', 'month_0']
folds = 11 if not is_debug else 2  # is_debug が True なら2, そうでなければ11
loss_type = 'rmse'
# competition_name = 'elo-merchant-category-recommendation'

# start log
now = datetime.datetime.now()
logging.basicConfig(
    filename='../logs/log_{0:%Y-%m%d-%H%M-%S}.log'.format(now),
    level=logging.DEBUG
)
logging.debug('../logs/log_{0:%Y-%m%d-%H%M-%S}.log'.format(now))
logging.debug('is_debug:{}'.format(is_debug))

# create features
if create_features:
    result = subprocess.run('python create_features.py', shell=True)
    if result.returncode != 0:
        print('ERROR: create_features.py')
        quit()

# create_features.py された特徴量のリストを取得(今は使ってない)
parser = argparse.ArgumentParser()
parser.add_argument('--config', default='features.json')
options = parser.parse_args()
feat_dict = json.load(open(options.config))
use_features = feat_dict['features']

# loading
path = cwd.replace(this_folder, '/features')
train_df, test_df = load_datasets(path, is_debug)

# 欠損値処理
train_df, test_df = removeMissingColumns(train_df, test_df, 0.5)
logging.debug("Train shape: {}, test shape: {}".format(train_df.shape, test_df.shape))

# model
"""
models, model_params, feature_importance_df, train_preds, test_preds, scores, model_name = kfold_lightgbm_without_outliers(
    train_df, test_df, target_col=target_col, model_loss=loss_type,
    num_folds=folds, feats_exclude=feats_exclude, stratified=False, use_gpu=use_GPU)
"""
models, model_params, feature_importance_df, train_preds, test_preds, scores, model_name = kfold_lightgbm(
    train_df, test_df, target_col=target_col, model_loss=loss_type,
    num_folds=folds, feats_exclude=feats_exclude, stratified=False, use_gpu=use_GPU)
"""
models, model_params, feature_importance_df, train_preds, test_preds, scores, model_name = kfold_xgb(
    train_df, test_df, target_col=target_col, model_loss=loss_type,
    num_folds=folds, feats_exclude=feats_exclude, stratified=False, use_gpu=use_GPU)
"""

# CVスコア
create_score_log(scores)

# submitファイルなどをまとめて保存します. ほんとはもっと疎結合にしてutilに置けるようにしたい...
def output(train_df, test_df, models, model_params, feature_importance_df, train_preds, test_preds, scores, now, model_name):
    score = sum(scores) / len(scores)
    folder_path = make_output_dir(score, now, model_name)
    for i, m in enumerate(models):
        save2pkl('{0}/model_{1:0=2}.pkl'.format(folder_path, i), m)
    with open('{0}/model_params.json'.format(folder_path), 'w') as f:
        json.dump(model_params, f, indent=4)
    with open('{0}/model_valid_scores.json'.format(folder_path), 'w') as f:
        json.dump({i:s for i, s in enumerate(scores)}, f, indent=4)
    save_importances(
        feature_importance_df,
        '{}/importances.png'.format(folder_path),
        '{}/importance.csv'.format(folder_path))
    # 以下の部分はコンペごとに修正が必要

    test_df.loc[:, 'target'] = test_preds
    test_df = test_df.reset_index()
    # targetが一定値以下のものをoutlierで埋める
    #q = test_df['target'].quantile(.0003)
    #q = 3
    #test_df.loc[:,'target']=test_df['target'].apply(lambda x: x if abs(x) > q else x-0.0001)
    test_df[['card_id', 'target']].to_csv(
        '{0}/submit_{1:%Y-%m%d-%H%M-%S}_{2}.csv'.format(folder_path, now, score),
        index=False
    )
    train_df.loc[:, 'OOF_PRED'] = train_preds
    train_df = train_df.reset_index()
    train_df[['card_id', 'OOF_PRED']].to_csv(
        '{0}/oof.csv'.format(folder_path),
    )

output(train_df, test_df, models, model_params, feature_importance_df, train_preds, test_preds, scores, now, model_name)
