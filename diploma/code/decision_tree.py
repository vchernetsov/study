import os
from abstracts import Strategy
from matplotlib import pyplot
from sklearn.tree import DecisionTreeClassifier as _DecisionTreeClassifier, plot_tree


class DecisionTreeClassifier(Strategy):
    model_class = _DecisionTreeClassifier
    model_name = 'Decision Tree'
    model_params = {
        'criterion': ['gini', 'entropy'],
        'max_depth': [3, 5, 7],
        'min_samples_split': [2, 3, 4],
        'min_samples_leaf': [1, 2, 4],
        'max_features': [None, 'sqrt', 'log2'],
    }
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
        pyplot.figure(figsize=(12, 20))
        plot_tree(self.model, filled=True, feature_names=feature_names, class_names=['Не горить', 'Горить'], rounded=True)
        pyplot.show()