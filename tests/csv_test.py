import csv

import pandas as pd


def test_csv_parse():
    print("test csv parse....")
    with open("resource/1.csv", "r") as csv_file:
        reader = csv.reader(csv_file)

        for item in reader:
            print(item)

        csv_file.close()


def test_csv_to_df():
    with open("resource/1.csv", "rb") as f:
        df = pd.read_csv(f)
        print(df)
