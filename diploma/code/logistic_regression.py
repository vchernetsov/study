from abstracts import Strategy
from sklearn.linear_model import LogisticRegression as _LogisticRegression


class LogisticRegression(Strategy):
    model_class = _LogisticRegression
    model_name = 'Logistic Regression'
    model_params = {
        'penalty': ['l1', 'l2', 'elasticnet', None],  # regularisation types
        'C': [0.01, 0.1, 1, 10, 100],  # regularisation coefficient
        'solver': ['liblinear', 'saga', 'ridge', 'lbfgs'],  # optimisers
        'max_iter': [100, 500, 1000],  # max iterations
        'l1_ratio': [0.01, 0.5, 0.75, 1],
    }

    def repr(self):
        super().repr()
        print("Полиномиальная модель:")
        print(f"z = {intercept:.2f} " + " + ".join(
            [f"{coeff:.2f}*{feature}" for coeff, feature in zip(coefficients, features)])
        )