import datetime
import pandas as pd
import pandas_datareader as web
from pytrends.request import TrendReq

# method to create the dataframe of signals
# - In: Ticker, Start date, End date
# - Out: Df with index=date, most recent trend score,
# rolling average volume (RAV), % change from prev RAV

# signal (True if: trend over last by 2x, over RAV)

# plan:
# - most recent trend score: already done in sanity_check (with ffill)
# - most recent trends score with no ffill so that pct_change works
# - <'Trend_Change'>change from previous trend score: series.pct_change()
# - rolling average volume --> df.rolling(window, min_periods)
# - <'Pct_Over_Prev_Volume'>change from previous RAV --> series.pct_change()
# - signal: apply(lambda row: ((row.Trend_Change > 200(%) and (row.volume > row.Pct_Over_Prev_Volume))

# for testing
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('use_inf_as_na', True)


# maybe also take in time, default to all of 2019
def tick_to_sig(company_name, ticker):
    # change these from being hardcoded once testing is done
    # for some reason, any range under 270 days long gives daily values
    start = datetime.datetime(2020, 1, 1)
    end = datetime.datetime(2020, 7, 15)

    # getting the data from yahoo finance for the given time period
    signal_df = web.DataReader(ticker, 'yahoo', start, end)
    signal_df = signal_df.rename(columns={'Adj Close': 'AdjClose'})

    # Calculate close price change day-to-day for back-testing
    signal_df['ClosePriceChangePercent'] = signal_df.AdjClose.pct_change() * 100
    signal_df = signal_df.drop(columns=['High', 'Low'])

    # Calculate Rolling Average Volume (past business week of data (5 days))
    #signal_df['RAV'] = signal_df['Volume'].rolling(window=5).mean()

    # Calculate current day's RAV change over previous days'
    signal_df['VolumeChangePercent'] = signal_df.Volume.pct_change() * 100

    # Building the trend signal from Google Trends
    pytr = TrendReq(hl='en-US', tz=360, geo='US')
    name_plus_robinhood = str(company_name) + " robinhood"
    kw_list = [name_plus_robinhood]
    pytr.build_payload(kw_list, timeframe='2020-1-1 2020-07-15')  # change this from being hardcoded once testing done
    # df containing weekly interest score for the given keyword
    df = pytr.interest_over_time()
    # df = df.drop(columns=['isPartial'])

    # merging together the two dfs by using their datestsla robinhood
    signal_df = pd.merge(signal_df, df, how='outer', left_index=True, right_index=True)

    # making a new column that fills in the weekday with the weekend's trend score so that there is a value
    # for the signal to grab every day
    signal_df[[name_plus_robinhood + "_filled"]] = signal_df[[name_plus_robinhood]].fillna(method='ffill')

    # Calculate current Trend score's percent change over the previous one
    signal_df['TrendChangePercent'] = signal_df[kw_list].pct_change().fillna(0) * 100

    # Calculate the raw gain in trend score from the previous day
    signal_df['TrendChangeRAW'] = signal_df[name_plus_robinhood].diff()

    # new column that forward fills trend change percent so that signal has a value every day
    # this is not needed when the ranges are short enough to have trend score for every day
    # signal_df['TrendChangePercent_filled'] = signal_df['TrendChangePercent'].fillna(method='ffill')

    # building the first attempt at a signal
    # consider adding limits to the upper and lower end of the trend number
    # also need to add a column that is just net change from the previous day
    # the reason for these ranges being capped is so that there's not TOO much attention on the stock which could
    # lead to a large unpredictable spike and then a crash as people sell off
    # Basically TRUE if large interest jump + volume jump
    signal_df['Bool_Signal'] = signal_df.apply(
        lambda row: (
                # we want an increase in attention but not too much
                (row.TrendChangeRAW >= 15 and row.TrendChangeRAW <= 55)
                and
                # we want a large in volume but also not too much
                (row.VolumeChangePercent > 250 and row.VolumeChangePercent < 600)),
        axis=1)

    return signal_df # [['Volume', 'VolumeChangePercent']]
    # this returns only the rows where the signal is true
    #return signal_df[[name_plus_robinhood, 'TrendChangeRAW']]
    #print(df.head(20))
    #print(signal_df[kw_list].head(20))
    #return signal_df[['Bool_Signal', 'hertz robinhood', 'TrendChangePercent_filled', 'RavChangePercent', 'RAV']]
    #return signal_df['Bool_Signal']

    # first condition
    # return signal_df.head(20)
    # return signal_df[['hertz robinhood','TrendChangePercent', 'RavChangePercent', 'Bool_Signal']]
# print(tick_to_sig("genius","GNUS"))


# finding the specific ranges of positive signal examples to look at
# start_date = datetime.datetime(2020, 5, 25)
# end_date = datetime.datetime(2020, 6, 11)
# df = tick_to_sig("genius", "GNUS")
# df = tick_to_sig("hertz", "HTZ")
# print(df[start_date:end_date])


sample_dict = {
    "HTZ": "hertz",
    "F": "ford",
    "AAPL": "apple"
}


# method that takes in df of signals and tells you how much you'd make if you bought
# at the close of the day of the signal and sold and the close of the next day
def calculate_earnings_pct(company_name, ticker):
    signal_df = tick_to_sig(company_name, ticker)
    #print(signal_df)
    signal_df_only_true = signal_df[signal_df.Bool_Signal]
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
    return percent_sum

#print(calculate_earnings_pct("hertz", "HTZ"))


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
    "Invesco": "IVR",
    "AMC": "AMC",
    "nokia": "NOK",
    "Catalyst": "CPRX",
    "Dave and busters": "PLAY",
    "iBio": "IBIO",
    "Gap": "GPS",
    "Sorrento": "SRNE",
    "macys": "M",
    "Everi": "EVRI",
    # "": "",
    "hertz": "HTZ",
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


# method that takes in dictionary of company names as coloquially searched and
# their corresponding ticker. Outputs the percentage returns as determined by
# the signal generated by the chosen method
def stock_to_result(dict_of_stocks):
    # make a dataframe with the index being the names of the companies
    return_df = pd.DataFrame({'Company': list(dict_of_stocks.keys())})
    return_df['Signal Return'] = return_df.apply(
        lambda row: calculate_earnings_pct(row.Company, dict_of_stocks[row.Company]), axis=1)
    return return_df

result = stock_to_result(cheap_stocks)
print(result)
print("here is the average return on your money")
print(result['Signal Return'].mean())


# look into testing if the signal works better if there is at least 1 or 2 or a couple 0's in
# the last 10 days of trading. These are stocks that we want to come "out of nowhere", not
# ones that are on the top of people's minds

