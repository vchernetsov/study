from abstracts import Strategy
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv2D, MaxPooling2D, Flatten, Dense, Dropout, Input
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    mean_absolute_error,
)
import numpy

class CNNClassifier(Strategy):
    model_name = 'Convolutional Neural Network'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, 'train_data') and hasattr(self, 'val_data'):
            self.scaler = StandardScaler()
            self.train_data = self.scaler.fit_transform(self.train_data)
            self.train_data = self.train_data.reshape(self.train_data.shape[0], 1, 9, 1)
            self.val_data = self.scaler.transform(self.val_data)
            self.val_data = self.val_data.reshape(self.val_data.shape[0], 1, 9, 1)

        self.model = Sequential([
            Input([1, 9, 1]),
            Conv2D(32, (1, 3), activation='relu'),
            MaxPooling2D(pool_size=(1, 2), padding='same'),
            Dropout(0.25),
            Conv2D(64, (1, 3), activation='relu'),
            MaxPooling2D(pool_size=(1, 2), padding='same'),
            Dropout(0.25),
            Flatten(),
            Dense(16, activation='relu'),
            Dropout(0.5),
            Dense(1, activation='sigmoid')
        ])
        self.model.compile(optimizer='adam',
                      loss='binary_crossentropy',
                      metrics=['accuracy'])

    def optimize(self, random_state=42, scoring='accuracy'):
        self.estimate()

    def fit(self):
        return self.model.fit(self.train_data, self.train_labels)

    def estimate(self):
        self.estimated_probability = self.model.predict(self.val_data)
        self.estimated = (self.estimated_probability > 0.5).astype("int32")

    def predict(self, data):
        scaled = self.scaler.transform(data)
        scaled = numpy.array(scaled)
        scaled = scaled.reshape(scaled.shape[0], 1, 9, 1)
        return super().predict(data=scaled)

    _metrics = None
    @property
    def metrics(self):
        if not self._metrics:
            train_estimated = (self.model.predict(self.train_data) > 0.5).astype("int32")
            train_accuracy = accuracy_score(self.train_labels, train_estimated)
            val_estimated = (self.model.predict(self.val_data) > 0.5).astype("int32")
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
            }
        return self._metrics