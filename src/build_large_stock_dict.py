import csv
import datetime
import pandas_datareader.data as web

stock_dict = {}
# import the csv I made with the terms I think are most likely to be searched with the corresponding company
with open('constituents_csv.csv', newline='') as csvfile:
    filereader = csv.reader(csvfile, delimiter=',')
    # row is a list that has each of the column elements as items
    # Make the first item the key in the dict and then everything else the value
    for row in filereader:
        stock_dict[(row[0])] = row[1:]


# adding the stock prices of the company so I can sort the results I get by price bucket
start_master = datetime.datetime(2020, 1, 1)
end_master = datetime.datetime(2020, 7, 20)
for item in stock_dict.keys():
    print(item)
    # get the dataframe containing stock price info
    ticker = stock_dict[item][0]
    try:
        price_df = web.DataReader(ticker, 'yahoo', start_master, end_master)
        # get the average price of the stock, grabbed the open here and took the average of the col
        average_price = price_df['Open'].mean()
        average_volume = price_df['Volume'].mean()
        # add more data to the stock's key/value pair (average price)
        stock_dict[item].append(average_price)
        stock_dict[item].append(average_volume)
        print(stock_dict[item])
    except Exception as e:
        stock_dict[item] = stock_dict[item].append(-1.00)

print(stock_dict)

with open('stock_dict_with_prices_and_names_and_volume.csv', 'w', newline='') as csv_file:
    writer = csv.writer(csv_file)
    for key, value in stock_dict.items():
        writer.writerow([key, value])

csvfile.close()
csv_file.close()











