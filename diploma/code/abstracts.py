import os
import re
import pandas
import pickle
import csv
import json
import numpy
from utils import NumpyEncoder

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    mean_absolute_error,
)
from striprtf.striprtf import rtf_to_text
from sklearn.model_selection import GridSearchCV

TABLE_PATTERN = re.compile(r'\d{1,2}\|.*\|')


class Pipeline:
    """Base class for all process pipelines."""
    data_path = 'data'  # path to data folder
    train_data = []
    val_data = []

    @property
    def path(self):
        """
        Generator function recursively passes OS folder and yields path to
        data file.
        """
        file_name = 'protA3.rtf'
        for (dir_path, _, filenames) in os.walk(self.data_path):
            if file_name in filenames:
                yield os.path.join(dir_path, file_name)

    @staticmethod
    def process_rtf(rtf_content):
        content = rtf_to_text(rtf_content)
        # remove "\r" windows-specific char
        content = content.replace("\r", "")
        # remove whitespaces
        content = re.sub(r"[ \t\r]+", " ", content)
        # split string with newline char
        data = content.split("\n")
        data = [x.strip() for x in data]
        for idx, line in enumerate(data):
            try:
                decoded_string = line.encode("latin1").decode("windows-1251")
                line = decoded_string
                data[idx] = line
                continue
            except:
                pass

            try:
                decoded_string = line.encode("windows-1251").decode("windows-1251")
                line = decoded_string
                data[idx] = line
                continue
            except:
                pass
            
        return list(filter(bool, data))

    def read_rtf(self, path):
        with open(path, "r", encoding="cp1257") as fh:
            rtf_content = fh.read()
            return self.process_rtf(rtf_content)

    @staticmethod
    def safe_converter(value, function=float, default=0.0):
        try:
            return function(value)
        except ValueError:
            return default

    def data_file_name(self, prefix):
        return os.path.join(self.data_path, f'{prefix}.csv')

    def save_data(self, prefix, data):
        with open(self.data_file_name(prefix), 'w', newline='') as fh:
            writer = csv.DictWriter(fh, fieldnames=data[0].keys())
            writer.writeheader()
            for row in data:
                writer.writerow(row)

    def restore_data(self, prefix):
        attr_name = f'{prefix}_data'
        setattr(self, attr_name, [])
        attr = getattr(self, attr_name)
        with open(self.data_file_name(prefix), newline='') as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                for key, value in row.items():
                    row[key] = numpy.float64(value)
                attr.append(row)


class BaseStrategy:
    model_class = None
    model_params = None
    optimal_params = None
    raw_model = None
    optimiser = None

    def __init__(self, train_data=None, val_data=None, model=None):
        super().__init__()
        if train_data and val_data:
            self.train_data = pandas.DataFrame(train_data)
            self.train_labels = self.train_data['factor']
            self.train_data = self.train_data.drop(columns=['factor'])
            self.val_data = pandas.DataFrame(val_data)
            self.val_labels = self.val_data['factor']
            self.val_data = self.val_data.drop(columns=['factor'])
        self.model = model

    def get_model(self, random_state):
        return self.model_class(random_state=random_state)

    def optimize(self, random_state=42, scoring='accuracy'):
        self.raw_model = self.get_model(random_state=random_state)
        self.optimiser = GridSearchCV(estimator=self.raw_model,
                                      param_grid=self.model_params,
                                      scoring=scoring,
                                      cv=5, verbose=1, n_jobs=-1)
        self.optimiser.fit(self.train_data, self.train_labels)
        self.optimal_params = self.optimiser.best_params_
        self.model = self.optimal_model
        self.estimate()

    @property
    def optimal_model(self):
        return self.optimiser.best_estimator_

    def predict(self, data):
        return self.model.predict(data)[0]

    def estimate(self):
        self.estimated = self.model.predict(self.val_data)
        self.estimated_probability = self.model.predict_proba(self.val_data)[:, 1]

    _metrics = None
    @property
    def metrics(self):
        if not self._metrics:
            train_estimated = self.model.predict(self.train_data)
            train_accuracy = accuracy_score(self.train_labels, train_estimated)
            val_estimated = self.model.predict(self.val_data)
            val_accuracy = accuracy_score(self.val_labels, val_estimated)
            self._metrics = {
                'accuracy': accuracy_score(self.val_labels, self.estimated),
                'precision': precision_score(self.val_labels, self.estimated),
                'recall': recall_score(self.val_labels, self.estimated),
                'f1': f1_score(self.val_labels, self.estimated),
                'roc_auc': roc_auc_score(self.val_labels, self.estimated_probability),
                'conf_matrix': confusion_matrix(self.val_labels, self.estimated),
                'mae': mean_absolute_error(self.val_labels, self.estimated),
                'train_accuracy': train_accuracy,
                'val_accuracy': val_accuracy,
                'overfit': (train_accuracy - val_accuracy) > 0.1,
                'estimated': self.estimated,
                'estimated_probability': self.estimated_probability,
            }
        return self._metrics

    def repr(self):
        metrics = self.metrics
        print(f"Accuracy: {metrics['accuracy']}")
        print(f"Precision: {metrics['precision']}")
        print(f"Recall: {metrics['recall']}")
        print(f"F1 Score: {metrics['f1']}")
        print(f"ROC AUC: {metrics['roc_auc']}")
        print(f"Mean Absolute Error (MAE): {metrics['mae']}")
        print(f"Confusion Matrix:\n{metrics['conf_matrix']}")
        if self.optimal_params:
            print(f"Best model params: {self.optimal_params}")


class StrategyIO:
    model_name = None
    model_path = 'models'

    @classmethod
    def model_file_name(cls):
        return os.path.join(cls.model_path, f'{cls.model_name}.model.pickle')

    @classmethod
    def model_scaler_file_name(cls):
        return os.path.join(cls.model_path, f'{cls.model_name}.scaler.pickle')

    @classmethod
    def restore_model(cls):
        """Factory method returning model instance"""
        with open(cls.model_file_name(), 'rb') as fh:
            model = pickle.load(fh)
            instance = cls(model=model)
        # upload scaler if possible
        if os.path.isfile(cls.model_scaler_file_name()):
            with open(cls.model_scaler_file_name(), 'rb') as fh:
                instance.scaler = pickle.load(fh)

        if os.path.isfile(cls.model_metrics_file_name()):
            with open(cls.model_metrics_file_name(), 'rb') as fh:
                instance._metrics = json.load(fh)

        return instance

    @classmethod
    def model_param_file_name(cls):
        return os.path.join(cls.model_path, f'{cls.model_name}.param.json')

    @classmethod
    def model_metrics_file_name(cls):
        return os.path.join(cls.model_path, f'{cls.model_name}.metric.json')

    def save_model(self):
        # save model itself
        with open(self.model_file_name(), 'wb') as fh:
            pickle.dump(self.model, fh)
        # save scaler
        if hasattr(self, 'scaler'):
            with open(self.model_scaler_file_name(), 'wb') as fh:
                pickle.dump(self.scaler, fh)
        # save model params
        with open(self.model_param_file_name(), 'w') as fh:
            json.dump(self.optimal_params, fh)
        # save model metrics
        with open(self.model_metrics_file_name(), 'w') as fh:
            json.dump(self.metrics, fh, cls=NumpyEncoder)


class Strategy(BaseStrategy, StrategyIO):
    pass


class ModelContext:
    strategies = []
    predicted = {}

    def __init__(self, classes, train_data, val_data):
        self.classes = classes
        self.train_data = train_data
        self.val_data = val_data

    def optimize(self):
        for cls in self.classes:
            strategy = cls(train_data=self.train_data, val_data=self.val_data)
            strategy.optimize()
            self.strategies.append(strategy)

    def save(self):
        for strategy in self.strategies:
            strategy.save_model()

    def restore(self):
        for cls in self.classes:
            instance = cls.restore_model()
            self.strategies.append(instance)

    def predict(self, data):
        for strategy in self.strategies:
            predicted = strategy.predict(data)
            self.predicted[strategy.model_name] = {
                'predicted': bool(predicted),
                'accuracy': strategy.metrics['accuracy'],
                'overfit': strategy.metrics['overfit']
            }