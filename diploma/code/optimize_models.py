import click
from abstracts import ModelContext
from constants import MODEL_CLASSES
from pipeline_data import DataPipeline


@click.command()
def optimize():
    """
    Ця програма призначена для оновлення математичних моделей.
    """
    ppl = DataPipeline()
    ppl.restore()
    ctx = ModelContext(classes=MODEL_CLASSES, train_data=ppl.train_data, val_data=ppl.val_data)
    ctx.optimize()
    ctx.save()

if __name__ == '__main__':
    optimize()
