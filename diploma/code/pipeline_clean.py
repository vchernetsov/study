import re

from abstracts import Pipeline
from constants import DROPLIST, TABLE_PATTERN


class CleanPipeline(Pipeline):
    def process(self):
        """The method iterates over the data folder and finds the differences between files."""
        self.maping = dict()
        for path in self.path:
            data = self.clean_file(path)
            data = list(filter(lambda x: x != '', data))
            if data:
                self.maping[path] = ','.join(data)

    def clean_file(self, path):
        data = self.read_rtf(path)
        for lineno, line in enumerate(data):
            line = line.strip()
            for drop_item in DROPLIST:
                if line.startswith(drop_item):
                    data[lineno] = ''
                    break
            if re.match(TABLE_PATTERN, line):
                data[lineno] = ''
        return data