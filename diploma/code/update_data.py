import click
from pipeline_data import DataPipeline


@click.command()
@click.option('--algo', help=("""Алгоритм розподілення даних для """
              """тренуваня моделей (за-замовченнямкожен 5ий рядок [threshold]), можна """
              """вказати ще випадковий підбір [random]"""), default=DataPipeline.ALGO_THRESHOLD)

def update(algo):
    """
    Ця програма призначена для оновлення даних. Якщо ви додали новий протокол 
    вимірювань та бажаете додати його до розрахунків моделей, виконайте цю
    программу.

    Для цього вона 
        * рекурсивно знаходить усi файли у дiректорії "./data" та знаходить файли
            протоколiв вимiрювань за ім'ям "protA3.rtf"
        * аналiзує кожен файл та читає таблицю вимiряних значень
        * пiсля цього вона зберiгає усi отриманi данi у виглядi '*.csv'
    """
    ppl = DataPipeline()
    ppl.load()
    ppl.split(algo=algo)
    ppl.save()


if __name__ == '__main__':
    update()
