import csv
import pandas as pd
from pathlib import Path

# Example data for 167 hours (you should replace this with your actual data)
def data_centre_profile(size): # size to be mentioned in kW
    df_load_profile = pd.read_csv(str(Path.cwd() / 'data' / 'profiles' / 'data_centre_hourly_week.csv'))
    df_load_profile = df_load_profile['Load_Profile'].div(50).mul(size)
    df_load_annual = pd.concat([df_load_profile]*70).to_frame().reset_index()
    df_load_annual = df_load_annual['Load_Profile'].to_frame()
  # Replace with your actual data

# Repeat data for the entire year (8760 hours)


# Prepare data in the format for CSV
    csv_data = []
    for hour in range(8760):
        value = df_load_annual['Load_Profile'][hour]  # Repeat data cyclically
        csv_data.append([hour + 1, value])  # Hour starts from 1

    csv_filename = str(Path.cwd() / 'data' / 'profiles' / 'yearly_data_centre_profile_repeated.csv')

    with open(csv_filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Hour', 'Load_Profile'])  # Header row
        writer.writerows(csv_data)

if __name__ == '__main__':
    size = 50
    data_centre_profile(size)