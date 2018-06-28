"""Parse CSV text *csv_segment* using parsing definition *pdef*:

   evaluate(rows, pdef)
"""
from enum import Enum, unique
import re

import pandas as pd

from util.csv_reader import read_csv
from extract.to_float import to_float
from extract.row_splitter import get_splitter

@unique
class State(Enum):
    INIT = 0
    DATA = 1
    HEADERS = 2

YEAR_CATCHER = re.compile("\D*(\d{4}).*")


def get_year(string: str, rx=YEAR_CATCHER):
    """Extracts year from *string* using *rx* regex.

       Returns:
           Year as integer
           False if year is not valid or not in plausible range."""
    match = re.match(rx, string)
    if match:
        year = int(match.group(1))
        if year >= 1991 and year <= 2050:
            return year
    return False

def is_year(string: str) -> bool:
    return get_year(string) is not False


def split_to_tables(rows):
    """Yield Tab() instances from *rows* list of lists."""
    datarows = []
    headers = []
    state = State.INIT
    for row in rows:
        # is data row?
        if is_year(row[0]):
            datarows.append(row)
            state = State.DATA
        else:
            if state == State.DATA:
                # table ended, emit it
                yield Table(headers, datarows)
                headers = []
                datarows = []
            headers.append(row)
            state = State.HEADERS
    # still have some data left
    if len(headers) > 0 and len(datarows) > 0:
        yield Table(headers, datarows)

def matches_at_start(x, pat):
    regex = r"\b{}".format(pat)
    return bool(re.search(regex, x))

def matches_anywhere(x, pat):
    return pat in x


def find(rows, patterns, comparison_func):
    return [pat
            for pat in patterns
            for row in rows
            if comparison_func(row[0], pat) ]
   
class Table:
    def __init__(self, headers, datarows, reader=None):
        self.headers = headers
        self.datarows = datarows
        self.name = None
        self.unit = None
        key = reader if reader else self.count_columns(self.datarows)
        self.splitter_func = get_splitter(key)
    
    @staticmethod
    def count_columns(datarows):
         """Number of columns in table."""
         return max([len(row[1:]) for row in datarows]) 
        
    def make_datapoint(self, value: str, time_stamp, freq):
        return dict(label=(self.name, self.unit),                    
                    value=to_float(value),
                    time_index=time_stamp,
                    freq=freq)    
    
    def yield_values(self):
        """Yield dictionaries with variable name, frequency, time_index
           and value. May yield a dictionary where d['value'] is None.
        """
        for row in self.datarows:
            year = get_year(row[0])
            data = row[1:]
            a_value, q_values, m_values = self.splitter_func(data)
            if a_value:
                time_stamp = timestamp_annual(year)
                yield self.make_datapoint(a_value, time_stamp, 'a')
            if q_values:
                for t, val in enumerate(q_values):
                    time_stamp = timestamp_quarter(year, t + 1)
                    yield self.make_datapoint(val, time_stamp, 'q')
            if m_values:
                for t, val in enumerate(m_values):
                    time_stamp = timestamp_month(year, t + 1)
                    yield self.make_datapoint(val, time_stamp, 'm')    
        
    def __repr__(self):
        return str(self.__dict__)


def timestamp_annual(year):
    return pd.Timestamp(year, 12, 31)


def timestamp_quarter(year, quarter):
    month = quarter * 3
    return timestamp_month(year, month) # .date()


def timestamp_month(year, month):
    return pd.Timestamp(year, month, 1) + pd.offsets.MonthEnd()


def make(csv_text: str, start='', end=''):
    rows = read_csv(csv_text)
    return list(split_to_tables(rows))

def assign_trailing_units(tables, required):
    tables = list(tables)
    for prev_table, table in zip(tables, tables[1:]):
        if (table.name is None 
            and table.unit in required[prev_table.name]):
            table.name = prev_table.name
            
def yield_values(tables):
   for t in tables:
       if t.name and t.unit:
           for x in t.yield_values():
               yield x

def assignments(tables):
    return [(t.name, t.unit) for t in tables]        
    

def var_parser(headers, name):
    def _enclosed(table):
        if find(table.headers, headers, matches_at_start):
            table.name = name
        return table    
    return _enclosed


def unit_parser(header, unit):
    def _enclosed(table):
        if find(table.headers, [header], matches_anywhere):
            table.unit = unit
        return table    
    return _enclosed

def complies(required, tables):
    req = [(name, unit) for name, units in required.items() for unit in units]
    tas = assignments(tables)
    return set(req) == set(tas) and len(req)  ==  len(tas)


def render(csv_rows, headers_dict, unit_dict, required):
    tables = split_to_tables(csv_rows)
    vparsers = [var_parser(headers, name) for name, headers in headers_dict.items()]
    uparsers = [unit_parser(header, unit) for header, unit in unit_dict.items()]
    for x in vparsers + uparsers:
        tables = map(x, tables)
    tables = list(tables)        
    assign_trailing_units(tables, required) 
    assert complies(required, tables)
    return list(yield_values(tables)) 
    
    
if __name__ == "__main__":  # pragma: no cover

    doc="""1.9. Ввод в действие жилых домов организациями всех форм собственности																	
    млн.кв.м общей площади																	
    1999	32,0	4,1	5,5	5,9	16,5	0,7	0,9	2,5	1,0	1,1	3,4	1,2	1,3	3,4	1,6	2,2	12,7
    2000	30,3	4,1	5,7	5,9	14,6	0,9	1,1	2,1	1,2	1,4	3,1	1,3	1,4	3,2	1,6	2,0	11,0    
    Объем ВВП, млрд.рублей / Gross domestic product, bln rubles
    1999	4823	901	1102	1373	1447
    в % к соответствующему периоду предыдущего года / percent of corresponding period of previous year
    1999	105,3	93,8	99,2	105,0	117,4	92,2	93,8	95,1	94,7	99,2	102,9	102,1	101,9	111,1	114,8	112,1	122,6
"""
    #TODO: convert parameters to this
    required1 = {'GDP': ['bln_rub', 'yoy'], 'DWELL': ['mln_m2']}     
    r1 = var_parser(name='GDP', headers=['Валовый внутренний продукт', 'Объем ВВП'])     
    r2 = var_parser(name='DWELL', headers=['Ввод в действие жилых домов организациями']) 
    u1 = unit_parser(header='млрд.рублей', unit='bln_rub')
    u2 = unit_parser(header='млн.кв.м общей площади', unit='mln_m2')
    u3 = unit_parser(header='% к соответствующему периоду предыдущего года', unit='yoy')                       
    
    tables = make(doc)
    for x in [u1, u2, u3, r1, r2]:
        tables = map(x, tables) 
    tables = list(tables)     
        
    print(assignments(tables))
    assign_trailing_units(tables, required1)
    print(assignments(tables))
    req = [(name, unit) for name, units in required1.items() for unit in units]
    assert set(req) == set(assignments(tables))
 
    values = list(yield_values(tables))
    csv_rows = read_csv(doc)
    values2 = render(csv_rows, 
           headers_dict={'GDP': ['Валовый внутренний продукт', 'Объем ВВП'],
                         'DWELL': ['Ввод в действие жилых домов организациями']},
           unit_dict={'млрд.рублей': 'bln_rub',
                        'млн.кв.м общей площади': 'mln_m2',
                        '% к соответствующему периоду предыдущего года': 'yoy'},
           required=required1)
    assert values == values2
            

    # example 1
    DOC = """Объем ВВП, млрд.рублей / Gross domestic product, bln rubles
1999	4823	901	1102	1373	1447
2000	7306	1527	1697	2038	2044"""
    tables = make(DOC)
    t = u1(r1(tables[0]))
    datapoints = list(t.yield_values())
    assert datapoints[0] == {'freq': 'a',
                             'label': ('GDP', 'bln_rub'),
                             'time_index': pd.Timestamp('1999-12-31'),
                             'value': 4823}
    assert datapoints[1] == {'freq': 'q',
                             'label': ('GDP', 'bln_rub'),
                             'time_index': pd.Timestamp('1999-03-31'),
                             'value': 901}
    assert datapoints[2] == {'freq': 'q',
                             'label': ('GDP', 'bln_rub'),
                             'time_index': pd.Timestamp('1999-06-30'),
                             'value': 1102}
    assert datapoints[3] == {'freq': 'q',
                             'label': ('GDP', 'bln_rub'),
                             'time_index': pd.Timestamp('1999-09-30'),
                             'value': 1373}
    assert datapoints[4] == {'freq': 'q',
                             'label': ('GDP', 'bln_rub'),
                             'time_index': pd.Timestamp('1999-12-31'),
                             'value': 1447}

    # example 2
    DOC = """	Год Year	Кварталы / Quarters	Янв. Jan.	Фев. Feb.	Март Mar.	Апр. Apr.	Май May	Июнь June	Июль July	Август Aug.	Сент. Sept.	Окт. Oct.	Нояб. Nov.	Дек. Dec.
		I	II	III	IV
1.7. Инвестиции в основной капитал1), млрд. рублей / Fixed capital investments1), bln rubles
1999	670,4	96,8	131,1	185,6	256,9	28,5	31,8	36,5	36,9	41,4	52,8	56,2	61,8	67,6	66,5	72,0	118,4
2000	1165,2	165,8	236,0	330,2	433,2	46,1	55,8	63,9	64,5	75,8	95,7	99,1	112,9	118,3	114,6	123,0	195,5
2001	1504,7	230,3	318,8	421,1	534,5	66,7	77,4	86,2	87,9	106,1	124,8	127,7	144,2	149,2	144,7	150,2	239,6
2002	1762,4	270,1	376,4	494,5	621,4	78,1	89,6	102,4	104,0	125,1	147,3	152,2	167,0	175,3	169,1	174,3	278,0
2003	2186,4	330,0	470,6	607,5	778,3	93,8	110,6	125,6	129,9	158,8	181,9	185,8	204,8	216,9	209,6	216,2	352,5
2004	2865,0	442,2	626,3	783,3	1013,2	124,1	149,9	168,2	170,7	209,2	246,4	236,8	270,5	276,0	264,9	290,9	457,4
2005	3611,1	540,5	776,3	993,6	1300,7	148,1	184,5	207,9	212,6	250,6	313,1	306,5	336,8	350,3	332,4	382,5	585,8
2006	4730,0	658,4	1017,6	1287,3	1766,7	176,3	217,5	264,6	267,8	340,6	409,2	381,5	437,6	468,2	462,9	508,6	795,2
2007	6716,2	897,6	1414,4	1744,1	2660,1	255,3	298,0	344,3	364,5	472,2	577,7	543,1	584,2	616,8	684,7	740,4	1235,0
2008	8781,6	1314,6	1991,5	2369,0	3106,5	364,3	447,3	503,0	544,1	672,2	775,2	725,5	782,0	861,5	879,0	877,4	1350,1
2009	7976,0	1224,3	1722,1	2061,0	2968,6	340,2	426,2	457,9	485,0	562,5	674,6	633,4	675,8	751,8	771,9	831,3	1365,4
2010	9152,1	1242,9	1962,5	2361,5	3585,2	331,7	421,5	489,7	527,2	642,2	793,1	683,9	794,7	882,9	931,2	977,7	1676,3
2011	11035,7	1422,0	2306,0	2854,1	4453,6	367,8	486,3	567,9	611,1	766,9	928,0	824,0	969,2	1060,9	1175,4	1192,3	2085,9
2012	12586,1	1730,1	2730,5	3225,0	4900,5	457,3	602,3	670,5	709,9	931,6	1089,0	976,6	1099,1	1149,3	1373,0	1303,3	2224,2
2013	13450,3	1905,4	2918,7	3402,9	5223,3	511,4	652,5	741,5	771,6	987,0	1160,1	1053,2	1147,2	1202,5	1449,9	1431,9	2341,5
2014	13902,6	1884,1	2985,0	3493,2	5540,3	492,2	650,2	741,7	779,4	1010,4	1195,2	1082,1	1178,8	1232,3	1507,8	1460,8	2571,7
2015	14555,9	1969,7	3020,8	3560,2	6005,2	516,9	680,7	772,1	812,8	1004,2	1203,8	1078,4	1209,1	1272,7	1703,9	1592,7	2708,6
20162)		2149,4	3153,3	3813,4
	Год Year	Кварталы / Quarters	Янв. Jan.	Фев. Feb.	Март Mar.	Апр. Apr.	Май May	Июнь June	Июль July	Август Aug.	Сент. Sept.	Окт. Oct.	Нояб. Nov.	Дек. Dec.
		I	II	III	IV
в % к соответствующему периоду предыдущего года / percent of corresponding period of previous year
1999	105,3	93,8	99,2	105,0	117,4	92,2	93,8	95,1	94,7	99,2	102,9	102,1	101,9	111,1	114,8	112,1	122,6
2000	117,4	113,5	119,6	119,7	116,1	107,9	116,1	115,7	116,5	122,1	120,0	116,9	122,5	119,6	118,2	118,5	113,4
2001	111,7	107,0	109,5	109,9	111,9	109,4	106,6	105,6	108,4	112,8	107,7	109,1	109,7	110,8	112,4	110,2	112,8
2002	102,9	101,3	103,5	102,7	103,1	100,1	100,1	103,4	103,7	103,3	103,5	104,1	101,5	102,8	103,2	102,9	103,2
2003	112,7	110,1	113,1	111,8	113,7	107,9	111,1	110,9	112,6	114,9	111,8	111,4	111,6	112,4	112,5	112,6	115,0
2004	116,8	118,4	116,9	111,8	111,2	117,5	119,6	118,1	116,0	115,7	118,6	110,9	114,4	110,1	108,2	114,7	110,8
2005	110,2	106,3	108,4	111,4	114,3	103,5	107,2	107,7	108,9	104,9	111,1	113,6	109,1	111,7	111,3	117,2	114,2
2006	117,8	108,8	117,7	116,1	120,3	106,6	105,0	113,7	112,8	121,9	117,8	111,8	116,7	119,3	123,8	117,6	120,0
2007	123,8	120,3	121,3	116,9	128,5	127,6	121,1	114,7	119,4	121,1	122,7	123,2	115,1	113,2	126,7	124,5	132,1
2008	109,5	123,4	117,6	112,3	98,7	120,9	126,1	123,0	125,0	119,1	111,6	110,8	110,5	115,4	106,9	99,7	93,5
2009	86,5	82,0	79,1	82,3	90,7	81,3	83,8	80,9	80,4	76,3	80,6	81,9	81,7	83,1	84,0	90,3	95,4
2010	106,3	95,2	105,6	105,3	111,1	91,7	92,5	100,4	101,7	105,6	108,3	99,5	108,1	107,8	110,6	108,0	113,3
2011	110,8	103,9	107,8	111,3	114,8	100,9	104,6	105,4	105,8	109,4	107,9	110,7	112,1	111,0	116,3	112,8	115,3
2012	106,8	113,9	110,6	105,5	103,2	116,3	116,0	110,6	108,4	113,9	109,3	110,2	106,2	101,2	109,4	102,9	99,9
2013	100,8	102,5	100,2	99,7	101,1	104,0	101,1	102,8	101,7	99,4	99,9	102,0	98,8	98,5	99,8	104,7	99,8
2014	98,5	96,9	100,2	99,8	97,3	94,1	97,6	98,2	99,6	100,9	100,1	101,3	98,0	100,2	100,1	94,7	97,1
2015	91,6	95,2	91,2	87,0	93,6	95,9	94,4	95,4	93,8	90,1	90,4	88,3	86,6	86,3	96,3	93,5	91,9
2016		95,2	96,1	100,3
в % к предыдущему периоду / percent of previous period
1999						42,5	108,4	111,2	97,2	109,2	124,3	102,6	106,2	104,1	95,1	104,3	161,3
2000						37,4	116,6	110,8	97,9	114,4	122,1	100,0	111,2	101,7	94,0	104,6	154,3
2001						35,7	113,6	109,8	100,5	119,1	116,5	101,3	111,8	102,7	95,3	102,5	158,0
2002						32,0	113,6	113,4	100,8	118,7	116,7	101,9	109,0	104,0	95,7	102,3	158,4
2003						33,5	117,0	113,2	102,3	121,2	113,6	101,5	109,3	104,7	95,8	102,4	161,8
2004		55,5	137,2	120,6	124,0	35,0	119,1	111,8	100,4	120,8	116,4	94,9	112,8	100,8	94,2	108,5	156,3
2005		51,9	139,9	123,9	127,2	32,0	123,3	112,3	101,5	116,4	123,4	97,0	108,3	103,2	93,8	114,3	152,3
2006		49,6	151,4	122,1	131,8	30,0	121,5	121,6	100,7	125,7	119,3	92,1	113,0	105,4	97,4	108,5	155,3
2007		49,4	152,6	117,7	144,9	31,7	115,3	115,2	104,8	127,5	120,9	92,5	105,6	103,7	109,0	106,6	164,9
2008		47,4	145,4	112,4	127,4	29,0	120,3	112,3	106,5	121,5	113,2	91,8	105,4	108,3	101,0	99,4	154,6
2009		39,4	140,3	116,9	140,5	25,2	124,0	108,4	106,0	115,3	119,5	93,4	105,2	110,1	102,1	106,8	163,4
2010		41,3	155,6	116,6	148,2	24,3	125,1	117,6	107,4	119,7	122,6	85,8	114,2	109,8	104,8	104,3	171,4
2011		38,7	161,0	120,6	153,0	21,6	129,8	118,4	107,6	123,8	121,0	88,1	115,7	108,8	109,8	101,1	175,2
2012		38,3	156,3	115,1	149,7	21,8	129,4	112,9	105,5	130,0	116,1	88,8	111,4	103,8	118,7	95,1	170,0
2013		38,1	152,8	114,4	151,9	21,1	125,8	114,9	104,3	127,1	116,6	90,7	107,9	103,5	120,2	99,8	162,1
2014		36,5	158,0	113,9	148,1	21,4	130,3	115,7	105,8	128,7	115,7	91,8	104,4	105,9	120,1	94,4	166,2
2015		35,2	152,1	108,9	160,4	20,7	129,1	116,4	104,2	123,0	118,2	87,8	105,3	103,6	134,3	92,9	163,0
2016		36,9	147,1	119,2
1.7.1. Инвестиции в основной капитал организаций"""
