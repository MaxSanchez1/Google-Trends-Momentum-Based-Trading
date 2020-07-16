import datetime
import pandas as pd
import pandas_datareader.data as web
import pytrends
import pandas as pd
from pytrends.request import TrendReq
from pandas import Series, DataFrame

# pd.set_option('display.max_rows', None)
# pytr = TrendReq(hl='en-US', tz=360)
# kw_list = ["Hertz Robinhood"]
# pytr.build_payload(kw_list)
# df = pytr.interest_over_time()
# print(df)

# iot_df = pytr.interest_over_time()
# print(iot_df)


# df = web.DataReader("AAPL", 'yahoo', start, end)


# building the sanity-check dataframe
# enter a list of stocks manually
# find the first instance of google trend score popping more than 2x its prev 20-day average
# and that becomes the data for
# col 1: stock ticker
# col 2: average google trend score over last 20 days
# col 2: average % stock change over next 5 days
# col 3:

# helper for building sanity-check
# - input: stock ticker
# - output: df with indexes for dates
#   - cols:
#       - prev 20-day average interest score
#       - current interest score
#       - prev 20-day stock price
#       - current stock price
#       - % delta over average stock price


# how well does "stock name" + "robinhood" interest score predict stock price
df_price_delta = pd.DataFrame()
# - get past year of stock price change in %, apple in this instance, year is all of 2019
start = datetime.datetime(2019, 1, 1)
end = datetime.datetime(2019, 12, 31)
close_price = web.DataReader("HTZ", 'yahoo', start, end)
close_price = close_price.rename(columns={'Adj Close': 'AdjClose'})
close_price['DeltaPct.'] = close_price.AdjClose.pct_change() * 100
close_price = close_price.drop(columns=['High', 'Low', 'Open', 'Close'])
# print(close_price)
# print(df_price_delta)
# - get past year of google trends interest
pytr = TrendReq(hl='en-US', tz=360)
kw_list = ["Hertz Robinhood"]
pytr.build_payload(kw_list, timeframe='2019-1-1 2019-12-31')
df = pytr.interest_over_time()
df = df.drop(columns=['isPartial'])
# print(df)

# merged = close_price.merge(df, left_on='Date', right_on='date', how='inner')
# merge_two = df.merge(close_price, how='left', left_index=True, right_index=True)
# print(merge_two)
merge_three = pd.merge(close_price, df, how='outer', left_index=True, right_index=True)
merge_three[['Hertz Robinhood']] = merge_three[['Hertz Robinhood']].fillna(method='ffill')
print(merge_three)
print(merge_three.corr())
