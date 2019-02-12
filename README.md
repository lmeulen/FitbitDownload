## Introduction ##
Download the fitbit data of a user. Data can be stored as CSV and/or SQLite database.

```bash usage: 
    download.py [-h] --id clientId --secret clientSecret
                   [--start STARTDATE] [--limit LIMIT]
                   [--first FIRSTDATE] 
                   [--online] [--offline] [--no-cache]`
```
- `--id id_client` : Fitbit client ID
- `--secret clientSecret` : Fitbit client secret
- `--first FIRSTDATE` : Oldest data Fitbit data is available
- `--start STARTDATE` : First day to download
- `--limit LIMIT` : Maximum number of days to download, going back in time starting at the specified first date
- `--online` : Connect tot Fitbit to download data
- `--offline` : Only use cached Fitbit API results
- `--no-cache` : Do not use local cached Fitbit API results

Only the first two arguments are mandatory. 

If no starting date is specified, the app starts downloading yesterday (since this is the last complete day of Fitbit logging). The default number of days ti downlaod is 7.
If data is already downloaded, it is read from the cache instead of the API (reduces use of the API and inproves speed),

## Dependencies ##
- ```python-fitbit```. Obtain from github (https://github.com/orcasgit/python-fitbit) and extract in the root of this app
- ```calmap```. Install with pip install calmap (only used in the notebooks)

## Data storage ##
During download, the following datastructure is created:
```bash
.
|- Cache                    # Cached responses, folder per year 
|  |- 2018
|  |- 2019
|
|- Data
|  |- fitbit.db             # SQLite database
|
|- Activities               # Activities information
|- Body                     # Body information
|- Calories                 # Calorie burned information
|- Daily                    # Daily summaries
|- Distance                 # Distance information
|- Elevation                # Elevation information
|- Floors                   # Floors climbed information
|- Heart                    # Heartrate information
|- Sleep                    # Sleep information
|- Steps                    # Steps information
```
- The cached responses are stored as JSON. The original repsonse is stored.
- The datafiles are stored as csv (per day).
- The database is in SQLite format.

## Notebooks ##
For educational purposes two notebooks are present. These use the SQLite database file as input.

## Database structure ##
```sql
CREATE TABLE `Steps_Summary` (
 `Date` TEXT,
 `Steps` TEXT
);

CREATE TABLE `Steps_1m` (
 `Date` TEXT,
 `Time` TEXT,
 `Steps` INTEGER
);

CREATE TABLE `Sleep_Summary` (
 `Date` TEXT,
 `Minutes Asleep` INTEGER,
 `Sleep Records` INTEGER,
 `Time in Bed` INTEGER,
 `Stage Deep` INTEGER,
 `Stage Light` INTEGER,
 `Stage REM` INTEGER,
 `Stage Wake` INTEGER
);

CREATE TABLE `Sleep_1m` (
 `Date` TEXT,
 `LogID` INTEGER,
 `Time` TEXT,
 `Value` TEXT,
 `interpreted` TEXT
);

CREATE TABLE `Sleep` (
 `Date` TEXT,
 `Log Count` INTEGER,
 `Start Time` TEXT,
 `End Time` TEXT,
 `Time In Bed` INTEGER,
 `Awake Count` INTEGER,
 `Awake Duration` INTEGER,
 `Awakenings Count` INTEGER,
 `Duration` INTEGER,
 `Efficiency` INTEGER,
 `Main Sleep` INTEGER,
 `Log ID` INTEGER,
 `Minutes After Wakeup` INTEGER,
 `Minutes Asleep` INTEGER,
 `Minutes Awake` INTEGER,
 `Minutes To Fall Asleep` INTEGER,
 `Restless Count` INTEGER,
 `Restless Duration` INTEGER
);

CREATE TABLE `Heartrate_Summary` (
 `Date` TEXT,
 `Resting Heart Rate` TEXT,
 `Zone0 Calories` REAL,
 `Zone0 Mxax` INTEGER,
 `Zone0 Min` INTEGER,
 `Zone0 Minutes` INTEGER,
 `Zone0  Name` TEXT,
 `Zone1 Calories` REAL,
 `Zone1 Max` INTEGER,
 `Zone1 Min` INTEGER,
 `Zone1 Minutes` INTEGER,
 `Zone1 Name` TEXT,
 `Zone2 Calories` REAL,
 `Zone2 Max` INTEGER,
 `Zone2 Min` INTEGER,
 `Zone2 Minutes` INTEGER,
 `Zone2 Name` TEXT,
 `Zone3 Calories` REAL,
 `Zone3 Max` INTEGER,
 `Zone3 Min` INTEGER,
 `Zone3 Minutes` INTEGER,
 `Zone3 Name` TEXT
);

CREATE TABLE `Heartrate` (
 `Date` TEXT,
 `Time` TEXT,
 `Heart Rate` INTEGER
);

CREATE TABLE `HeartRate_Zones` (
 `Date` TEXT,
 `Name` TEXT,
 `ID` INTEGER,
 `Minutes` INTEGER,
 `Calories` REAL,
 `Min` INTEGER,
 `Max` INTEGER
);

CREATE TABLE `Floors_1m` (
 `Date` TEXT,
 `Time` TEXT,
 `Floors` INTEGER
);

CREATE TABLE `Elevation_1m` (
 `Date` TEXT,
 `Time` TEXT,
 `Elevation` REAL
);

CREATE TABLE `Distance_1m` (
 `Date` TEXT,
 `Time` TEXT,
 `Distance` REAL
);

CREATE TABLE `Distance` (
 `Date` TEXT,
 `Activity` TEXT,
 `Distance` REAL
);

CREATE TABLE `Daily_Summary` (
 `Date` TEXT,
 `Goal Active Minutes` INTEGER,
 `Goal Calories Out` INTEGER,
 `Goal Distance` INTEGER,
 `Goal Floors` INTEGER,
 `Goal Steps` INTEGER,
 `Active Score` INTEGER,
 `Steps` INTEGER,
 `Distance` REAL,
 `Elevation` REAL,
 `Floors` INTEGER,
 `Resting Heart Rate` INTEGER,
 `Activity Calories` INTEGER,
 `Calories BMR` INTEGER,
 `Marginal Calories` INTEGER,
 `Calories Out` INTEGER,
 `Sedentary Minutes` INTEGER,
 `Lightly Active Minutes` INTEGER,
 `Fairly Active Minutes` INTEGER,
 `Very Active Minutes` INTEGER,
 `Minutes Asleep` INTEGER,
 `Sleep Records` INTEGER,
 `Time in Bed` INTEGER,
 `Stage Deep` INTEGER,
 `Stage Light` INTEGER,
 `Stage REM` INTEGER,
 `Stage Wake` INTEGER,
 `Zone0 Calories` REAL,
 `Zone0 Mxax` INTEGER,
 `Zone0 Min` INTEGER,
 `Zone0 Minutes` INTEGER,
 `Zone0  Name` TEXT,
 `Zone1 Calories` REAL,
 `Zone1 Max` INTEGER,
 `Zone1 Min` INTEGER,
 `Zone1 Minutes` INTEGER,
 `Zone1 Name` TEXT,
 `Zone2 Calories` REAL,
 `Zone2 Max` INTEGER,
 `Zone2 Min` INTEGER,
 `Zone2 Minutes` INTEGER,
 `Zone2 Name` TEXT,
 `Zone3 Calories` REAL,
 `Zone3 Max` INTEGER,
 `Zone3 Min` INTEGER,
 `Zone3 Minutes` INTEGER,
 `Zone3 Name` TEXT,
 `Sleep Start Time` TEXT,
 `Sleep End Time` TEXT,
 `Sleep Time In Bed` INTEGER,
 `Sleep Awake Count` INTEGER,
 `Sleep Awake Duration` INTEGER,
 `Sleep Awakenings Count` INTEGER,
 `Sleep Duration` INTEGER,
 `Sleep Efficiency` INTEGER,
 `Sleep Minutes After Wakeup` INTEGER,
 `Sleep Minutes Asleep` INTEGER,
 `Sleep Minutes Awake` INTEGER,
 `Sleep Minutes To Fall Asleep` INTEGER,
 `Sleep Restless Count` INTEGER,
 `Sleep Restless Duration` INTEGER
);

CREATE TABLE `Calories_1m` (
 `Date` TEXT,
 `Time` TEXT,
 `Calories` REAL
);

CREATE TABLE `Body` (
 `Date` TEXT,
 `Weight` REAL,
 `Bodyfat` REAL,
 `BMI` REAL
);

CREATE TABLE `Activities_Summary` (
 `Date` TEXT,
 `Goal Active Minutes` INTEGER,
 `Goal Calories Out` INTEGER,
 `Goal Distance` INTEGER,
 `Goal Floors` INTEGER,
 `Goal Steps` INTEGER,
 `Active Score` INTEGER,
 `Steps` INTEGER,
 `Distance` REAL,
 `Elevation` REAL,
 `Floors` INTEGER,
 `Resting Heart Rate` INTEGER,
 `Activity Calories` INTEGER,
 `Calories BMR` INTEGER,
 `Marginal Calories` INTEGER,
 `Calories Out` INTEGER,
 `Sedentary Minutes` INTEGER,
 `Lightly Active Minutes` INTEGER,
 `Fairly Active Minutes` INTEGER,
 `Very Active Minutes` INTEGER
);

```