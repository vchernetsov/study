from abstracts import Strategy
from sklearn.neighbors import KNeighborsClassifier as _KNeighborsClassifier
from sklearn.preprocessing import StandardScaler


class KNeighborsClassifier(Strategy):
    model_class = _KNeighborsClassifier
    model_name = 'K nearest neighbors'
    model_params = {
        'n_neighbors': [3, 5, 7, 9],
        'weights': ['uniform', 'distance'],
        'metric': ['euclidean', 'manhattan', 'minkowski'],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, 'train_data') and hasattr(self, 'val_data'):
            self.scaler = StandardScaler()
            self.train_data = self.scaler.fit_transform(self.train_data)
            self.val_data = self.scaler.transform(self.val_data)

    def get_model(self, random_state):
        return self.model_class(**self.model_params)

    def predict(self, data):
        """
        Method overrides parent`s class method. As long as KNN is
        need to ba scaled, let`s do it here
        """
        scaled = self.scaler.transform(data)
        return super().predict(data=scaled)