import pandas as pd
import datetime
import logging
from sklearn.model_selection import KFold
#import argparse
import json
import subprocess
import os
import sys
cwd = os.getcwd()
sys.path.append(cwd.replace('/user01',''))
from lgbmClassifier import train_and_predict
from utils import log_best, load_datasets, load_target, save2pkl


#parser = argparse.ArgumentParser()
#parser.add_argument('--config', default='model_params.json')
#options = parser.parse_args()
#config = json.load(open(options.config))


now = datetime.datetime.now()
logging.basicConfig(
    filename='../logs/log_{0:%Y-%m-%d-%H-%M-%S}.log'.format(now), level=logging.DEBUG
)
logging.debug('../logs/log_{0:%Y-%m-%d-%H-%M-%S}.log'.format(now))

#feats = config['features']
#logging.debug(feats)

#target_name = config['target_name']


X_train_all, X_test = load_datasets(feats)
y_train_all = load_target(target_name)
logging.debug(X_train_all.shape)


y_preds = []
models = []

lgbm_params = {
    "learning_rate": 0.1,
    "num_leaves": 8,
    "boosting_type": "gbdt",
    "colsample_bytree": 0.65,
    "reg_alpha": 1,
    "reg_lambda": 1,
    "objective": "multiclass",
    "num_class": 2
}

kf = KFold(n_splits=3, random_state=0)
for train_index, valid_index in kf.split(X_train_all):
    X_train, X_valid = (
        X_train_all.iloc[train_index, :], X_train_all.iloc[valid_index, :]
    )
    y_train, y_valid = y_train_all[train_index], y_train_all[valid_index]

    # lgbmの実行
    y_pred, model = train_and_predict(
        X_train, X_valid, y_train, y_valid, X_test, lgbm_params
    )

    # 結果の保存
    y_preds.append(y_pred)
    models.append(model)

    # スコア
    log_best(model, config['loss'])

# CVスコア
scores = [
    m.best_score['valid_0'][config['loss']] for m in models
]
score = sum(scores) / len(scores)

# モデルの保存
for i, model in enumerate(models):
    save2pkl('../models/lgbm_{0}_{1}.pkl'.format(score, str(i)), model)

# モデルパラメータの保存
with open('../models/lgbm_{0}_params.json'.format(score), 'w') as f:
    json.dump(lgbm_params, f, indent=4)

print('===CV scores===')
print(scores)
print(score)
logging.debug('===CV scores===')
logging.debug(scores)
logging.debug(score)

# submitファイルの作成
ID_name = config['ID_name']
sub = pd.DataFrame(pd.read_csv('../data/input/test.csv')[ID_name])

for i in range(len(y_preds) - 1):
    y_preds[0] += y_preds[i + 1]

sub[target_name] = [1 if y > 1 else 0 for y in y_preds[0]]

sub.to_csv(
    '../data/output/submit_{0:%Y-%m-%d-%H-%M-%S}_{1}.csv'.format(now, score),
    index=False
)