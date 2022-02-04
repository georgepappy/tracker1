import pandas as pd
import numpy as np
import sqlite3
import requests
from bs4 import BeautifulSoup, SoupStrainer
from datetime import date, datetime

path = '/Users/georgepappy/Documents/Metis/online_flex/Module7_DataEngineering/project_sandbox/tracker_1/'


##################
# The method/code below using BeautifulSoup to access
# all .csv files in a GitHub Repository is adapted from:
#
# https://stackoverflow.com/questions/69806371/combining-all-csv-files-from-github-repository-link-and-make-it-a-one-csv-file
##################


##################
# 1) Get State-wide Covid Data
##################

con = sqlite3.connect(path + 'covid.db')

# Read in state population data
states = pd.read_csv(path + 'states.csv')[['State', 'Pop2021']]
states.columns = ['Province_State', 'pop2021']

# Get data from GitHub
html = requests.get('https://github.com/CSSEGISandData/COVID-19/blob/master/csse_covid_19_data/csse_covid_19_daily_reports_us')

# Check to see if state_data table exists and get most recent date of update
query = con.execute(
          """
              SELECT name FROM sqlite_master WHERE type="table" AND name="state_data";
          
          """).fetchone() 

if query != None:
    query = con.execute(
              """
                  SELECT MAX(last_update) FROM state_data;
              
              """).fetchone()
    last_update = datetime.strptime(query[0].split()[0], "%Y-%m-%d").date()
else:
    # Just starting to fill an empty table - set last_update variable way back in the past
    last_update = date(1980, 1, 1)

    
# Fetch data from Johns Hopkins GitHub repository
for link in BeautifulSoup(html.text, parse_only=SoupStrainer('a'), features="lxml"):
    if hasattr(link, 'href') and link['href'].endswith('.csv'):
        
        # Only add this file if new (i.e. not in database already)
        if datetime.strptime(link["title"].replace(".csv", ""), "%m-%d-%Y").date() > last_update:     
            url = 'https://github.com'+link['href'].replace('/blob/', '/raw/')
            df = pd.read_csv(url, sep=',', lineterminator='\n')
            
            # Drop rows we're not interested in (e.g. The Cruise Ships with outbreaks, Minor Outlying US Territories)
            df = df[~df['Province_State'].isin(['Diamond Princess', 'Grand Princess', 'American Samoa', 'Recovered', 
                                                'Virgin Islands', 'Guam', 'Northern Mariana Islands', 'Puerto Rico'])]
            
            # Account for slight modifications to column nomenclature that occurred over time
            if 'Mortality_Rate' in df.columns:
                df.rename({'Mortality_Rate' : 'Case_Fatality_Ratio', 'People_Tested' : 'Total_Test_Results'}, axis=1, inplace=True)
    
            # Retain only columns of interest
            df = df.iloc[:, 0:14].drop(columns=['Recovered', 'Active', 'FIPS', 'Total_Test_Results', 'People_Hospitalized'])
            
            # Add 2021 population column
            df = df.merge(states[['pop2021', 'Province_State']], how='left', on='Province_State')
            
            # Convert the date-time text column into a proper date object (time of day not really of interest)
            df['Last_Update'] = pd.to_datetime(df['Last_Update']).dt.date
            
            # drop data into database
            df.to_sql('state_data', con, if_exists='append', index=False)

##################


##################
# 2) Get County-wide Covid Data
##################

# Read in county population data
counties = pd.read_csv(path + 'counties.csv', skiprows=4, sep='\t').reset_index()
counties.columns = ['county', 'state', 'pop2021', 'pop2010', 'growth']
counties['county'] = counties['county'].apply(lambda x: x.replace(' County', ''))
counties = counties[['county', 'state', 'pop2021']]
counties['pop2021'] = counties['pop2021'].apply(lambda x: int(x.replace(',', '')))
counties['Combined_Key'] = counties['county'] + ', ' + counties['state'] + ', US'


# Get data from GitHub
html = requests.get('https://github.com/CSSEGISandData/COVID-19/blob/master/csse_covid_19_data/csse_covid_19_daily_reports')

# Check to see if state_data table exists and get most recent date of update
query = con.execute(
          """
              SELECT name FROM sqlite_master WHERE type="table" AND name="county_data";
          
          """).fetchone() 

if query != None:
    query = con.execute(
              """
                  SELECT MAX(last_update) FROM county_data;
              
              """).fetchone()
    last_update = datetime.strptime(query[0].split()[0], "%Y-%m-%d").date()
else:
    # Just starting to fill an empty table - set last_update variable way back in the past
    last_update = date(1980, 1, 1)

for link in BeautifulSoup(html.text, parse_only=SoupStrainer('a'), features="lxml"):
    if hasattr(link, 'href') and link['href'].endswith('.csv'):
        
        # Only add this file if new (i.e. not in database already)
        if datetime.strptime(link["title"].replace(".csv", ""), "%m-%d-%Y").date() > last_update:        
            url = 'https://github.com'+link['href'].replace('/blob/', '/raw/')
            df = pd.read_csv(url, sep=',', lineterminator='\n')
            
            # Only process this df if it contains the 'Combined_Key' - Otherwise, it's from very early in the pandemic (the schema evolved)
            if 'Combined_Key' in df.columns:
            
                # Drop rows not associated with our list of US counties & retain only the columns of interest
                df = df[df['Combined_Key'].isin(counties['Combined_Key'])].iloc[:, 0:12].drop(columns=['FIPS', 'Country_Region', 'Recovered', 'Active'])
                
                # Add 2021 population column
                df = df.merge(counties[['pop2021', 'Combined_Key']], how='left', on='Combined_Key')
            
                # Compute 'Incident_Rate' & 'Case_Fatality_Ratio' (schema evolved over time, so we drop them above when found & compute all of them from scratch here)
                df['Incident_Rate'] = 100000 * df['Confirmed'] / df['pop2021']
                df['Case_Fatality_Ratio'] = 100 * df['Deaths'] / df['Confirmed']
                
                # Convert the date-time text column into a proper date object (time of day not really of interest)
                df['Last_Update'] = pd.to_datetime(df['Last_Update']).dt.date
            
                # drop data into database
                df.to_sql('county_data', con, if_exists='append', index=False)


con.close()