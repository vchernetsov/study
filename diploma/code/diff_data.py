import click
from pipeline_clean import CleanPipeline

@click.command()
def update():
    """
    Ця програма призначена для пошуку різниці у файлах протоколів.
    """

    cpp = CleanPipeline()
    cpp.process()
    for key, value in cpp.maping.items():
        print (key)
        print (value)
        print('*' * 80)

if __name__ == '__main__':
    update()
