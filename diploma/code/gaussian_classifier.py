from abstracts import Strategy
from sklearn.naive_bayes import GaussianNB as _GaussianNB


class GaussianNB(Strategy):
    model_class = _GaussianNB
    model_name = 'GaussianNB'
    model_params = {
        'var_smoothing': [1e-9, 1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2,],
    }

    def get_model(self, random_state):
        return self.model_class()

    def repr(self):
        super().repr()
        priors = self.model.class_prior_
        theta = self.model.theta_
        print (f'Априорные вероятности классов: {priors[0]:.2f} - горить, {priors[1]:.2f} - не горить')
        print ('Средние значения признаков для класса - горить')
        for coeff, feature in zip(self.model.theta_[0], features):
             print (coeff, feature)
        print ('Средние значения признаков для класса - не горить')
        for coeff, feature in zip(self.model.theta_[1], features):
             print (coeff, feature)