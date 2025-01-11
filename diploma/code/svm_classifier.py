from abstracts import Strategy
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC as _SVC


class SVMClassifier(Strategy):
    model_class = _SVC
    model_name = 'Support Vector Classifier'
    model_params = {
        'C': [0.1, 1, 10, 100],
        'kernel': ['linear', 'rbf', 'poly', 'sigmoid'],
        'gamma': ['scale', 'auto', 0.01, 0.1],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, 'train_data') and hasattr(self, 'val_data'):
            self.scaler = StandardScaler()
            self.train_data = self.scaler.fit_transform(self.train_data)
            self.val_data = self.scaler.transform(self.val_data)

    def get_model(self, random_state):
        return self.model_class(probability=True)

    def predict(self, data):
        """
        Method overrides parent`s class method. As long as KNN is
        need to ba scaled, let`s do it here
        """
        scaled = self.scaler.transform(data)
        return super().predict(data=scaled)