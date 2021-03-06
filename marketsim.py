import argparse
import datetime as dt
import numpy as np
import QSTK.qstkutil.qsdateutil as du
import QSTK.qstkutil.tsutil as tsu
import QSTK.qstkutil.DataAccess as da
import pandas as pd
import QSTK.qstkstudy.EventProfiler as ep
import eventstudies as es


class MarketSim(object):

    def __init__(self, output_path, start_date=None, end_date=None,
                 symbols=None,
                 orders_file=None, cash=1000000, **kwds):
        self.cash = cash
        self.output_path = output_path
        self.orders = None
        self.symbols = symbols
        self.start_date = start_date
        self.end_date = end_date
        if orders_file:
            self.set_from_file(orders_file)

        self.open_market_days = du.getNYSEdays(
            self.start_date,
            self.end_date + dt.timedelta(days=1),
            dt.timedelta(hours=16))
        self.d_data = self.get_data(self.start_date, self.end_date, self.symbols)
        self.na_closing_prices = self.d_data['close'].values
        self.bollinger_bands = self.get_bollinger_bands()

        if orders_file:
            self.daily_values = self.get_daily_values()
            # import pdb;pdb.set_trace()

    def set_from_file(self, orders_file):
        self.orders = self.create_order_array(orders_file)
        self.symbols = np.unique(self.orders['symbol'])

        f = self.orders[0]
        l = self.orders[-1]
        self.start_date = dt.datetime(f['year'], f['month'], f['day'])
        self.end_date = dt.datetime(l['year'], l['month'], l['day'])

    def generate_daily_values_file(self):
        np.savetxt(output_path, self.daily_values, fmt='%i', delimiter=',')

    def get_bollinger_bands(self, lookback=20):
        rolling_mean = pd.rolling_mean(self.na_closing_prices, lookback)
        rolling_std = pd.rolling_std(self.na_closing_prices, lookback)
        bollinger_bands = (self.na_closing_prices - rolling_mean) / rolling_std
        df_bollinger = pd.DataFrame(bollinger_bands, index=self.open_market_days,
                                    columns=self.symbols)
        return df_bollinger

    def get_daily_values(self):
        cash = self.cash
        symbols = self.symbols
        open_market_days = self.open_market_days
        na_closing_prices = self.na_closing_prices

        portfolioHoldings = {}
        na_daily_values = np.zeros([len(open_market_days), 4])
        for symbol in symbols:
            portfolioHoldings[symbol] = 0

        portfolioValues = np.zeros((len(open_market_days), len(symbols)))
        for day in open_market_days:
            close_index = open_market_days.index(day)
            for order in self.orders:
                date = dt.datetime(order['year'], order['month'], order['day'])
                if day.date() == date.date():
                    symbol = order['symbol']
                    orderType = order['orderType']
                    shares = order['shares']
                    symbol_index = np.where(symbols == symbol)
                    stock_price = na_closing_prices[close_index][symbol_index]
                    if symbol not in portfolioHoldings:
                        portfolioHoldings[symbol] = 0

                    if orderType.lower() == 'buy':
                        portfolioHoldings[symbol] += shares
                        cash -= (stock_price * shares)
                    elif orderType.lower() == 'sell':
                        portfolioHoldings[symbol] -= shares
                        cash += (stock_price * shares)
                    else:
                        raise Exception('Bad Order Type')
            # pdb.set_trace()
            for symbol in symbols:
                symbol_index = np.where(symbols == symbol)
                portfolioValues[close_index][symbol_index] = (
                    na_closing_prices[close_index][symbol_index] *
                    (float(portfolioHoldings[symbol])))
            # pdb.set_trace()
            dailyValue = np.sum(np.nan_to_num(portfolioValues[close_index])) + cash
            na_daily_values[close_index] = [day.year, day.month,
                                            day.day, dailyValue]

        return na_daily_values

        # print len(na_closing_prices)
        # print len(rolling_mean)
        # print len(rolling_std)
        # print na_closing_prices[-5:]
        # raw_input(benchmarkPortfolio)
        # numbers_to_plot = np.zeros([len(open_market_days), 2])
        # numbers_to_plot[:, 0] = na_daily_values[:, 3]
        # numbers_to_plot[:, 1] = benchmarkPortfolio[:]
        # raw_input(numbers_to_plot)
        # plt.clf()
        # plt.plot(open_market_days, numbers_to_plot)
        # plt.legend(['My portfolio', '$SPX'])
        # plt.ylabel('Adjusted Close')
        # plt.xlabel('Date')
        # plt.savefig('My Portfolio.pdf', format='pdf')
        # print 'Saved PDF to "My Portfolio.pdf"'

    def get_data(self, start_date, end_date, symbols):
        hours = dt.timedelta(hours=16)
        open_market_days = du.getNYSEdays(start_date, end_date + dt.timedelta(days=1), hours)
        c_dataobj = da.DataAccess('Yahoo', cachestalltime=0)
        file_columns = ['open', 'high', 'low', 'close', 'volume', 'actual_close']
        file_data = c_dataobj.get_data(open_market_days, symbols, file_columns)
        d_data = dict(zip(file_columns, file_data))
        return d_data

    def create_order_array(self, orders_file):
        dtype = [('year', int), ('month', int), ('day', int),
                 ('symbol', 'S10'), ('orderType', 'S10'), ('shares', int)]
        na_orders = np.loadtxt(orders_file, delimiter=',', dtype=dtype)
        na_orders = np.sort(na_orders, order=['year', 'month', 'day'])
        return na_orders

    def report_output(self):
        na_daily_values = self.daily_values
        start_date = dt.datetime(int(na_daily_values[0, 0]), int(na_daily_values[0, 1]), int(na_daily_values[0, 2]))
        end_date = dt.datetime(int(na_daily_values[-1, 0]), int(na_daily_values[-1, 1]), int(na_daily_values[-1, 2]))

        total_return = na_daily_values[-1, 3] / na_daily_values[0, 3]
        na_daily_returns = na_daily_values.copy()[:, 3]
        tsu.returnize0(na_daily_returns)
        standard_deviation = np.std(na_daily_returns)
        average_daily_returns = np.average(na_daily_returns)
        sharpe_ratio = (average_daily_returns / standard_deviation *
                        np.sqrt(252))

        na_bench_prices = self.get_data(start_date, end_date, ['$SPX'])['close'].values
        benchmarkPortfolio = na_bench_prices[:, 0]
        na_benchmark_daily_returns = benchmarkPortfolio.copy()
        tsu.returnize0(na_benchmark_daily_returns)
        benchmark_total_return = benchmarkPortfolio[-1] / benchmarkPortfolio[0]
        benchmark_standard_deviation = np.std(na_benchmark_daily_returns)
        benchmark_average_daily_returns = np.average(na_benchmark_daily_returns)
        benchmark_sharpe_ratio = (benchmark_average_daily_returns / benchmark_standard_deviation *
                                  np.sqrt(252))

        print '\n'
        print ('The final value of the portfolio using the sample file is -- ' +
               str(end_date.date()) + ', ' + str(int(na_daily_values[-1, 3])))
        print ''
        print 'Details of the Performance of the portfolio :'
        print ''
        print 'Data Range : ' + str(start_date.date()) + ' to ' + str(end_date.date())
        print ''
        print 'Sharpe Ratio of Fund : ' + str(sharpe_ratio)
        print 'Sharp Ratio of $SPX : ' + str(benchmark_sharpe_ratio)
        print ''
        print 'Total Return of Fund : ' + str(total_return)
        print 'Total Return of $SPX : ' + str(benchmark_total_return)
        print ''
        print 'Standard Deviation of Fund : ' + str(standard_deviation)
        print 'Standard Deviation of $SPX : ' + str(benchmark_standard_deviation)
        print ''
        print 'Average Daily Return of Fund : ' + str(average_daily_returns)
        print 'Average Daily Return of $SPX : ' + str(benchmark_average_daily_returns)
        print '\n'


def parse_args():
    '''Defines command line arguments and parses them into variables'''

    parser = argparse.ArgumentParser(
        description="Runs script for given school and semester")
    parser.add_argument('cash', help="Starting Portfolio Amount")
    parser.add_argument('orders_file', help="CSV with orders")
    parser.add_argument('values_file', help="Output Path")
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    orders_file = args.orders_file
    output_path = args.values_file
    cash = int(args.cash)

    # Start Bollinger Event Study
    dataobj = da.DataAccess('Yahoo')
    ls_symbols = dataobj.get_symbols_from_list('sp5002012')
    ls_symbols.append('SPY')
    sim = MarketSim('output.csv',
                    start_date=dt.datetime(2008, 1, 1),
                    end_date=dt.datetime(2009, 12, 31),
                    symbols=ls_symbols)
    boll_data = sim.get_bollinger_bands()
    df_events = es.find_bollinger_events(ls_symbols, boll_data)
    ep.eventprofiler(df_events, sim.d_data, i_lookback=20, i_lookforward=20,
                     s_filename='2012Bollinger.pdf', b_market_neutral=True,
                     b_errorbars=True, s_market_sym='SPY')
    # End Bollinger Event Study

    # Start Backtest
    sim = MarketSim(orders_file=orders_file, output_path=output_path, cash=cash)
    sim.generate_daily_values_file()
    sim.report_output()
