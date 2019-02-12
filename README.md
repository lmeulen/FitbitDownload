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

If no starting date is specified, the app starts with dwonloading yesterday since this is the last complete day of Fitbit logging.

## Dependencies ##
- fitbit-api. Obtain from github abd extract in the root of this app
- calmap. Install with pip install calmap (only used in the notebooks)

## Data storage ##
During download, the following datastructure is created:
```bash
.
|- Cache                    # Cached responses, folder per year 
|  |- 2018
|  |- 2019
|- Data
|  |- fitbit.db             # SQLite database
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