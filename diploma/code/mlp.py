from abstracts import Strategy
from sklearn.neural_network import MLPClassifier as _MLPClassifier


class MLPClassifier(Strategy):
    model_class = _MLPClassifier
    model_name = 'Multi Layer Perceptron'
    model_params = {
        'hidden_layer_sizes': [
            (8, 8),
            (8, 16),
            (8, 16),
            (16, 32),
            (16),
            (16, 16),
            (16, 32),
            (64),
            (32, 64),
        ],
        'activation': ['relu', 'tanh'],
        'solver': ['adam', 'sgd'],
        'alpha': [0.0001, 0.001, 0.01],
        'learning_rate': ['constant', 'adaptive'],
        'batch_size': [32, 64],
    }
