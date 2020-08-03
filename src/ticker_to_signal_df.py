import datetime
import pandas as pd
import pandas_datareader as web
from pytrends.request import TrendReq
from datetime import timedelta
from dateutil.relativedelta import *
import numpy as np


# for testing
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('use_inf_as_na', True)

start_master = datetime.datetime(2020, 1, 1)
end_master = datetime.datetime(2020, 7, 20)
# this is how to get only the date for filling in "timeframe" in pytr
# print(start_master.strftime('%Y-%m-%d'))

# Calculate a trading signal given the input data and some given parameters
def tick_to_sig(company_name, ticker, start, end):
    # getting the data from yahoo finance for the given time period
    signal_df = web.DataReader(ticker, 'yahoo', start, end)
    # signal_df = signal_df.rename(columns={'Adj Close': 'AdjClose'})

    # Calculate close price change day-to-day for back-testing
    # signal_df['ClosePriceChangePercent'] = signal_df.AdjClose.pct_change() * 100
    signal_df = signal_df.drop(columns=['High', 'Low'])

    # Calculate Rolling Average Volume (past business week of data (5 days))
    #signal_df['RAV'] = signal_df['Volume'].rolling(window=5).mean()

    # Calculate current day's RAV change over previous days'
    signal_df['VolumeChangePercent'] = signal_df.Volume.pct_change() * 100

    # Building the trend signal from Google Trends
    # pytr = TrendReq(hl='en-US', tz=360, geo='US')
    # got rate limited so I have to change it to this for the time being
    pytr = TrendReq(hl='en-US', tz=360, timeout=(10,25), proxies=['https://34.203.233.13:80',], retries=2, backoff_factor=0.1, requests_args={'verify':False})
    name_plus_robinhood = str(company_name) + " stock"
    kw_list = [name_plus_robinhood]
    tf = start.strftime('%Y-%m-%d') + " " + end.strftime('%Y-%m-%d')
    pytr.build_payload(kw_list, timeframe=tf)
    # df containing weekly interest score for the given keyword
    df = pytr.interest_over_time()
    # df = df.drop(columns=['isPartial'])

    # merging together the two dfs by using their dates
    signal_df = pd.merge(signal_df, df, how='outer', left_index=True, right_index=True)

    # Calculate current Trend score's percent change over the previous one
    # signal_df['TrendChangePercent'] = signal_df[kw_list].pct_change().fillna(0) * 100

    # these fail if there's not enough data when the trend score is calculated, return an empty df in that case
    try:
        # Calculate the raw gain in trend score from the previous day
        signal_df['TrendChangeRAW'] = signal_df[name_plus_robinhood].diff()

        # calculate the local maximum within the given period
        signal_df['LocalMax'] = signal_df[name_plus_robinhood].cummax()

        # calculate the difference in cumulative maximum day to day to find outlier days where the local max went up a lot
        signal_df['LocalMaxChange'] = signal_df['LocalMax'].diff()
    except KeyError:
        signal_df['TrendChangeRAW'] = 0
        signal_df['LocalMax'] = 0
        signal_df['LocalMaxChange'] = 0

    # looking for a trend that is significant but isn't too high. We want to buy from here until the next peak or
    # for some amount of days after where there is no peak.
    # TODO: write something that counts the number of consecutive "TRUE"s and stop trading at a certain cutoff (10?)
    signal_df['Bool_Temp'] = signal_df.apply(
        lambda row: (row.LocalMax > 20 and row.LocalMax < 55)
                    # and
                    # this is so we don't use the entire period until the next peak, just one day
                    # this strategy is much more volatile without this but it could be more profitable
                    #(row.LocalMaxChange > 0)
        , axis=1)

    # TESTING: column that figures out how many trues there are in a row in the bool signal column
    signal_df['reset'] = signal_df.apply(
        lambda row: 0 if row.Bool_Temp else 1, axis=1)
    signal_df['val'] = signal_df.apply(
        lambda row: 1 if row.Bool_Temp else 0, axis=1)

    signal_df['cumsum'] = signal_df['reset'].cumsum()
    signal_df['consecutive_days_true'] = signal_df.groupby(['cumsum'])['val'].cumsum()
    signal_df = signal_df.drop(columns=['cumsum', 'reset', 'val'])

    signal_df['Bool_Signal'] = signal_df.apply(
        # TODO: put this back to 3-15
        lambda row: True if (row.Bool_Temp) else False, axis=1)

    return signal_df
#
# # TODO: when presenting, explain that this prediction could work for something like hertz because pop was more gradual
# TODO:     whereas the genius pop happened too fast so that 36 hour delay was too much and the data was essentially useless
# print(tick_to_sig("hertz","HTZ", start_master, end_master))
# print(tick_to_sig("genius","GNUS", start_master, end_master))
# print(tick_to_sig("tesla","TSLA", start_master, end_master))
# print(tick_to_sig("aurora","ACB", start_master, end_master))


# finding the specific ranges of positive signal examples to look at
# start_date = datetime.datetime(2020, 5, 20)
# end_date = datetime.datetime(2020, 6, 11)
# # df = tick_to_sig("genius", "GNUS")
# # df = tick_to_sig("hertz", "HTZ")
# print(df[start_date:end_date])


sample_dict = {
    "HTZ": "hertz",
    "F": "ford",
    "AAPL": "apple"
}


# method that takes in df of signals and tells you how much you'd make if you bought
# at the close of the day of the signal and sold and the close of the next day
def calculate_earnings_pct(company_name, ticker, start, end):
    print(company_name)
    signal_df = tick_to_sig(company_name, ticker, start, end)
    #print(signal_df)
    signal_df_only_true = signal_df[signal_df.Bool_Signal]
    # print(len(signal_df_only_true.index))
    # print(signal_df_only_true)
    # cumulative change in percent if the signal is followed
    percent_sum = 0
    for index, row in signal_df_only_true.iterrows():
        # new method -----
        # - buy at open of next trading day
        # - sell at the closing of the day after that
        date = index

        # need to get the open of the next trading day and make sure it's not null
        next_open = signal_df.iloc[signal_df.index.get_loc(date)+1]['Open']
        # if it's null it's usually because signal was on a friday and this is a weekend day. This fixes that
        if not pd.notna(next_open):
            next_open = signal_df.iloc[signal_df.index.get_loc(date)+3]['Open']
        # there are some 3-day weekends for the trading floor, this covers that edge case
        if not pd.notna(next_open):
            next_open = signal_df.iloc[signal_df.index.get_loc(date)+4]['Open']

        # need to get the close price of the day after (eg. flag on monday (night), buy at tues open, sell at wed close)
        close_two_after_flag = signal_df.iloc[signal_df.index.get_loc(date)+2]['Close']
        # if this runs into a weekend by 1 day (eg. tries to grab a sunday)
        if not pd.notna(close_two_after_flag):
            close_two_after_flag = signal_df.iloc[signal_df.index.get_loc(date)+3]['Close']
        # if this runs into a weekend by 2 days (eg. tries to grab a saturday)
        if not pd.notna(close_two_after_flag):
            close_two_after_flag = signal_df.iloc[signal_df.index.get_loc(date)+4]['Close']
        # if this runs into a weekend by 3 days (eg. tries to grab the closed friday of a trading holiday)
        if not pd.notna(close_two_after_flag):
            close_two_after_flag = signal_df.iloc[signal_df.index.get_loc(date)+5]['Close']

        # now calculating returns using the found values that shouldn't be able to be nans
        # print("Bought at:")
        # print(next_open)
        # print("Sold at:")
        # print(close_two_after_flag)
        percent_sum += float((close_two_after_flag - next_open) / next_open) * 100
        # print(percent_sum)
    return percent_sum

# print(calculate_earnings_pct("genius", "GNUS", start_master, end_master))
# print(calculate_earnings_pct("hertz", "HTZ", start_master, end_master))


# mostly stocks from "most popular under $15" from robinhood
# tried to use what the easiest way to search a stock would be
# eg. Cronos instead of "Cronos Financial"
cheap_stocks = {
    "ford": "F",
    "GE": "GE",
    "American Airlines": "AAL",
    "gopro": "GPRO",
    "aurora": "ACB",
    "plug power": "PLUG",
    "NIO": "NIO",
    "zynga": "ZNGA",
    "Aphria": "APHA",
    "Marathon": "MRO",
    "MFA": "MFA",
    "AMC": "AMC",
    "nokia": "NOK",
    "Catalyst": "CPRX",
    "Dave and busters": "PLAY",
    "Gap": "GPS",
    "Sorrento": "SRNE",
    "macys": "M",
    # "": "",
    # this works really really well of course but it is probably just overtuned to this
    # "hertz": "HTZ",
    "genius": "GNUS",
    "apple": "AAPL",
    "tesla": "TSLA",
    "microsoft": "MSFT",
    "disney": "DIS",
    "amazon": "AMZN",
    "snapchat": "SNAP",
    "uber": "UBER",
    "facebook": "FB",
}

top_100_rh = {

}


# method that takes in dictionary of company names as coloquially searched and
# their corresponding ticker. Outputs the percentage returns as determined by
# the signal generated by the chosen method
def stock_to_result(dict_of_stocks, start, end):
    # make a dataframe with the index being the names of the companies
    return_df = pd.DataFrame({'Company': list(dict_of_stocks.keys())})
    return_df['Signal Return'] = return_df.apply(
        lambda row: calculate_earnings_pct(row.Company, dict_of_stocks[row.Company], start, end), axis=1)
    return return_df

# result = stock_to_result(cheap_stocks, start_master, end_master)
# print(result)
# print("here is the average return on your money")
# print(result['Signal Return'].mean())


# forward-looking signal alert
# - find today's date and subtract 7 months from it. That's the start and today is the end.
# - plug that start and end into tick_to_sig
# - if the bottom row that we have historical data for (36 hours ago) is true, we buy and we hold until the next peak
# - or until 10 days after the signal has been true consecutively


def forward_looking_signal(company_name, ticker):
    # today
    end_local = datetime.datetime.now()
    # 7 months before today
    start_local = end_local + relativedelta(months=-7)
    # running the signal generation
    signal_dataframe = tick_to_sig(company_name, ticker, start_local, end_local)
    # usually guaranteed to have data from 4 days ago
    print(signal_dataframe.tail(4))


# print(forward_looking_signal("apple", "AAPL"))



# building new stock dict to crunch data and then compare it with its stock price and volume to see if
# there are any trends
# csv --> df
big_df = pd.read_csv('stock_dict_with_prices_and_names_and_volume.csv')
# drop the rows we don't have tickers for
big_df = big_df.dropna(subset=['ticker'], axis=0)
# get rid of the weird formatting so it's just the ticker
big_df['ticker'] = big_df['ticker'].apply(
    lambda tick: str(tick)[2:len(tick)-1]
)
# get rid of the bracket at the end and cast to int for readability
big_df['average_volume'] = big_df['average_volume'].apply(
    lambda aver: int(float(str(aver)[1:len(aver)-1]))
)

# add series containing the gain/loss in percent for the strategy
big_df['ROI_with_signal'] = big_df.apply(
    lambda row: calculate_earnings_pct(row.short_name, row.ticker, start_master, end_master)
    , axis=1
)

print("Here's the big results:")

# what is the average return on investment with the strategy
print("Average Return:")
print(big_df['ROI_with_signal'].mean())

# how does stock price correlate with the strategy
print("Correlation between ROI and price")
print(big_df['ROI_with_signal'].corr(big_df['average_price']))

# how does volume correlate with the stratgey
print("Correlation between ROI and volume")
print(big_df['ROI_with_signal'].corr(big_df['average_volume']))


#print(big_df)






