from abstracts import Strategy
from matplotlib import pyplot
from sklearn.ensemble import RandomForestClassifier as _RandomForestClassifier
from sklearn.tree import plot_tree
import numpy
import os


class RandomForestClassifier(Strategy):
    model_class = _RandomForestClassifier
    model_name = 'Random Forest'
    model_params = {
        'n_estimators': [100, 200, 500],
        'max_depth': [3, 5, 7],
        'min_samples_split': [2, 3, 4],
        'min_samples_leaf': [1, 2, 4],
        'max_features': [None, 'sqrt', 'log2'],
        'bootstrap': [True, False],
        'class_weight': ['balanced', 'balanced_subsample']
    }

    @property
    def optimal_model(self):
        """Pick the best tree from forest"""
        forest = super().optimal_model
        best_tree = None
        best_score = -numpy.inf
        for tree in forest:
            tree_score = tree.score(self.val_data, self.val_labels)
            if tree_score > best_score:
                best_score = tree_score
                best_tree = tree
        return best_tree

    @classmethod
    def model_image_file_name(cls):
        return os.path.join(cls.model_path, f'{cls.model_name}.tree.png')

    def save_model(self):
        super().save_model()
        feature_names = list(self.train_data.columns)
        pyplot.figure(figsize=(12, 10))
        plot_tree(self.model, filled=True, feature_names=feature_names, class_names=['Не горить', 'Горить'], rounded=True)
        pyplot.savefig(self.model_image_file_name())

    def repr(self):
        super().repr()
        feature_names = list(self.train_data.columns)
        pyplot.figure(figsize=(12, 10))
        plot_tree(self.model, filled=True, feature_names=feature_names,class_names=['Не горить', 'Горить'], rounded=True)
        pyplot.show()
