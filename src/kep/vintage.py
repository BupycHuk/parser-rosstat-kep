"""Extract dataframes by year and month."""

from kep import FREQUENCIES, PARSING_DEFINITION
from kep.parsing_definition.checkpoints import CHECKPOINTS, validate
from kep.helper.path import InterimCSV, ProcessedCSV
from kep.helper.date import Date
from kep.csv2df.dataframe_maker import Datapoints

class Vintage:
    """Represents dataset release for a given year and month.
        Performs interim CSV file parsing on construction and obtains 
        resulting dataframes.
    """
    def __init__(self, year: int, month: int, parsing_definition=PARSING_DEFINITION):
        self.year, self.month = year, month
        csv_text = InterimCSV(year, month).text()
        parsing_definition.attach_data(csv_text)
        emitter = Datapoints(parsing_definition.tables)
        self.dfs = {freq: emitter.get_dataframe(freq) for freq in FREQUENCIES}

    def save(self, folder=None):
        csv_processed = ProcessedCSV(self.year, self.month, folder)
        for freq, df in self.dfs.items():
            path = csv_processed.path(freq)
            df.to_csv(path)
            print("Saved dataframe to", path)

    def validate(self):
        for freq in FREQUENCIES:
            df = self.dfs[freq]
            checkpoints = CHECKPOINTS[freq]
            validate(df, checkpoints)
        print("Test values parsed OK for", self)

    def __repr__(self):
        return "Vintage({}, {})".format(self.year, self.month)


class Latest(Vintage):
    """Operations on most recent data release."""

    def __init__(self, year: int, month: int):
        super().__init__(year, month)
        # protect from using old realeses of data 
        Date(year, month).assert_latest()

    def upload(self, password: str):        
        # TODO: upload to database
        raise NotImplementedError

    def save(self, folder=None):
        ProcessedCSV(self.year, self.month).to_latest()

    def to_xls(self, folder=None):
        # TODO: upload to database
        raise NotImplementedError


if __name__ == "__main__": # pragma: no cover
    v = Vintage(2016, 10)
    v.validate()
    # Expected:
    # Test values parsed OK for Vintage(2016, 10)
