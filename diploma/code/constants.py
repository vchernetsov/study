import re
from logistic_regression import LogisticRegression
from gaussian_classifier import GaussianNB
from knn_classifier import KNeighborsClassifier
from svm_classifier import SVMClassifier
from random_forest import RandomForestClassifier
from decision_tree import DecisionTreeClassifier
from mlp import MLPClassifier
from cnn import CNNClassifier


MODEL_CLASSES = [
    LogisticRegression,
    GaussianNB,
    KNeighborsClassifier,
    SVMClassifier,
    RandomForestClassifier,
    DecisionTreeClassifier,
    MLPClassifier,
    CNNClassifier,
]


DEFAULT_SQUARE = 0.0
SQUARE_MAP = {}
try:
    from square_map import DEFAULT_SQUARE, SQUARE_MAP
except ImportError:
    pass


OK_FACTORS = [
    'Горит',
    'Маленький факел',
    'АИ-450М горит',
    'горит',
    'Ćīščņ',
]

TABLE_PATTERN = re.compile(r'\d{1,2}\|.*\|')

DROPLIST = [
    'Дата',
    'Распорядительный',
    'Шифр',
    'Конструктивные',
    'Воспламенитель',
    'Приспособление',
    'a-время',
    'Агрегат',
    'Корпус',
    'Пусковая',
    'Свеча',
    'Термопара tвоспл установлена',
    'Термопара tф установлена:',
    'Измеряемые и расчетные параметры:',
    '№реж|Время|Н',
    'км|DPккж',
    'мм.вод.ст|DPп.т.',
    'кгс/см2|tвозд',
    'С|tп.т.',
    'С|tфак.',
    'С|t x фак',
    'сек|tф2',
    'С|t x ф2',
    'сек|tвосп',
    'С|t x вос',
    'сек| Е',
    'Дж| t',
    'Гц|',
    'Горение|Циклограмма|Задерж.',
    'воспл, сек|Примечание|',
    '|||||||||||||||| а| b| c| d|tay| N|N1|||',
    'сек|DP',
    'ккж1|tф2',
    '||||||||||||||||| а| b| c| d|tay| N|N1|||',
    '№реж|Время|DPккж',
    '||||||||||||||| а| b| c| d|tay| N|N1|||',
]
