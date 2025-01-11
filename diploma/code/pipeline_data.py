from abstracts import Pipeline, TABLE_PATTERN
import re
from copy import deepcopy
import random
from constants import DEFAULT_SQUARE, SQUARE_MAP, OK_FACTORS


class DataPipeline(Pipeline):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.raw_data = []

    def load(self):
        for protocol in self.protocols:
            for line in self.clean(protocol):
                self.raw_data.append(line)

    ALGO_RANDOM = 'random'
    ALGO_THRESHOLD = 'threshold'
    def split(self, algo=ALGO_RANDOM, ratio=0.8, threshold=5):
        dataset = deepcopy(self.raw_data)
        if algo == self.ALGO_RANDOM:
            random.shuffle(dataset)
            limit = int(len(dataset) * ratio)
            train_data = dataset[:limit]
            val_data = dataset[limit:]
        elif algo == self.ALGO_THRESHOLD:
            train_data = []
            val_data = []
            for index, value in enumerate(dataset):
                if index % threshold != 0:
                    train_data.append(value)
                else:
                    val_data.append(value)
        else:
            raise NotImplementedError('Unknown data split algorithm')
        self.train_data = train_data
        self.val_data = val_data

    def clean(self, protocol):
        square = DEFAULT_SQUARE
        path = protocol['path']
        if path in SQUARE_MAP:
            square = SQUARE_MAP[path]
        initial = {
            'square': square,
            # 'path': path,
            # 'device_type': protocol['device_type'],
            # 'igniter': protocol['igniter'],
        }
        for item in protocol['data']:
            data = deepcopy(initial)
            data['altitude'] = self.safe_converter(item[2])
            data['delta_p_kk'] = self.safe_converter(item[3])
            data['delta_p_fuel'] = self.safe_converter(item[4])
            data['air_temp'] = self.safe_converter(item[5])
            data['fuel_temp'] = self.safe_converter(item[6])
            data['torch_temp'] = self.safe_converter(item[7])
            data['torch_time'] = self.safe_converter(item[8])
            data['ignition_temp'] = self.safe_converter(item[11])
            factor = 0
            if item[-1] in OK_FACTORS:
                factor = 1
            # data['factor'] = factor
            data['factor'] = factor
            yield data

    @property
    def protocols(self):
        for path in self.path:
            data = self.read_rtf(path)
            protocol = self.parse_protocol(data)
            protocol['path'] = path
            yield protocol

    def parse_protocol(self, data):
        def finder(feature, data=data):
            for line in data:
                line = line.strip()
                if feature(line):
                    return line.split(':')[1].strip()

        response = {}
        response['date'] = finder(lambda x: x.startswith('Дата'))
        response['device_type'] = finder(lambda x: x.startswith('Приспособление'))
        response['igniter'] = finder(lambda x: x.startswith('Воспламенитель'))
        response['body'] = finder(lambda x: x.startswith('Корпус'))
        response['nozzle'] = finder(lambda x: x.startswith('Пусковая форсунка'))
        response['spark'] = finder(lambda x: x.startswith('Свеча зажигания'))
        response['ignitor-unit'] = finder(lambda x: x.startswith('Агрегат зажигания'))
        response['ignitor-place'] = finder(lambda x: 'tвоспл' in x)
        response['torch-place'] = finder(lambda x: 'tф' in x)
        response['square'] = DEFAULT_SQUARE
        response['data'] = []
        for line in data:
            if re.match(TABLE_PATTERN, line):
                row = line.split('|')[:-1]
                response["data"].append(row)
        return response

    def save(self):
        self.save_data('train', self.train_data)
        self.save_data('val', self.val_data)

    def restore(self):
        self.restore_data('train')
        self.restore_data('val')