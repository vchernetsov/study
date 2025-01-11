import click
import numpy as numpy

from abstracts import ModelContext
from pipeline_data import DataPipeline
from constants import MODEL_CLASSES
from colored import Back, Style
import tabulate

@click.command()
@click.option('--square', help='Площа отвору розпалювача (поле: square)', type=numpy.float64, required=True)
@click.option('--altitude', help='Висота польоту (поле: altitude)', type=numpy.float64, required=True)
@click.option('--delta-p-kk', help='Перепад тиску у кільцевому каналі (поле: delta_P_kk)', type=numpy.float64, required=True)
@click.option('--delta-p-fuel', help='Перепад тиску палива (поле: delta_P_fuel)', type=numpy.float64, required=True)
@click.option('--air-temp', help='Температура повітря (поле: air_temp)', type=numpy.float64, required=True)
@click.option('--fuel-temp', help='Температура палива (поле: fuel_temp)', type=numpy.float64, required=True)
@click.option('--torch-temp', help='Температура факела горения (поле: torch_temp)', type=numpy.float64, required=True)
@click.option('--torch-time', help='Час факела горения (поле: torch_time)', type=numpy.float64, required=True)
@click.option('--ignition-temp', help='Температура воспламенения (поле: ignition_temp)', type=numpy.float64, required=True)
def optimize(square, altitude, delta_p_kk, delta_p_fuel, air_temp, fuel_temp,
             torch_temp, torch_time, ignition_temp):
    """
    Ця програма призначена для передбачення даних математичних моделей.
    Приклад використання
    python estimate_data.py --square=32 --altitude=0.0 --delta-p-kk=95 --delta-p-fuel=3.5 --air-temp=2 --fuel-temp=-34.0 --torch-temp=64 --torch-time=2 --ignition-temp=85
    """
    ppl = DataPipeline()
    ppl.restore()
    ctx = ModelContext(classes=MODEL_CLASSES, train_data=ppl.train_data, val_data=ppl.val_data)
    ctx.restore()
    raw_data = {
        'square': square,
        'altitude': altitude,
        'delta_p_kk': delta_p_kk,
        'delta_p_fuel': delta_p_fuel,
        'air_temp': air_temp,
        'fuel_temp': fuel_temp,
        'torch_temp': torch_temp,
        'torch_time': torch_time,
        'ignition_temp': ignition_temp,
    }
    data = [numpy.array(list(raw_data.values()))]
    ctx.predict(data)
    output = []
    factor_positive = factor_negative = 0
    for model_name, value in ctx.predicted.items():
        prediction = value['predicted']
        accuracy = value['accuracy']
        overfit = value['overfit']
        accuracy_color = Back.GREEN
        if accuracy <= 0.8 or overfit:
            prediction_color = accuracy_color = Back.GREY_37
        else:
            if prediction:
                prediction_color = Back.GREEN
                factor_positive += 1
            else:
                prediction_color = Back.red
                factor_negative += 1
        model_message = f'{accuracy_color}{model_name}{Style.reset}'
        prediction_message = f'{prediction_color}Горить{Style.reset}'
        if not prediction:
            prediction_message = f'{prediction_color}Не горить{Style.reset}'
        accuracy_message = f'{accuracy_color}{accuracy}{Style.reset}'
        overfit_message = f'Ні'
        if overfit:
            overfit_message = f'Так'
        output.append([model_message, prediction_message, accuracy_message, overfit_message])
    print(tabulate.tabulate(output, headers=['Модель', 'Передбачення', 'Точність моделі', 'Перенавчена'], tablefmt="fancy_grid"))
    factor_num = factor_positive + factor_negative
    print (f'Таким чином, із {factor_num} точних моделей {factor_positive} передбачило позитивний результат, а {factor_negative} - негативний')
    return ctx.predicted


if __name__ == '__main__':
    optimize()
