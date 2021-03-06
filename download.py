import os
import json
import argparse
import time
import traceback
import datetime
import sqlite3
import fitbit
import gather_keys_oauth2 as Oauth2
import pandas as pd

# Switch for debug messages from the cache
DEBUG_CACHE = False


def create_directories():
    """
    Create required directories for storing cache, CSV data and SQLite database
    :return:
    """
    data_directories = ["Sleep", "Steps", "Floors", "Calories", "Distance", "Heart", "Activities",
                        "Elevation", "Body", "Daily", "Data", "Training"]
    for dir_name in data_directories:
        create_directory_if_not_exist(dir_name)

    data_directories = ["Cache"]
    years = ["2017", "2018", "2019"]
    for dir_name in data_directories:
        for year in years:
            create_directory_if_not_exist(dir_name, year)


def create_directory_if_not_exist(directory, subdirectory=None):
    """
    Create directory if it does not exist
    :param directory: name of directory to create
    :param subdirectory: subdirectory of directory to create
    :return:
    """
    if subdirectory:
        dir_name = os.path.join(directory, subdirectory)
    else:
        dir_name = directory
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)


def get_dict_element(dictionary, key1, key2=None, key3=None):
    """
    Return an item from a dictionary, maximum three levels deep. Keys
    can be integers or strings.
    Can also handle lists
    :param dictionary: Dictionary
    :param key1: First level key
    :param key2: Second level key
    :param key3: Third level key
    :return:
    """
    try:
        if key3:
            return dictionary[key1][key2][key3]
        elif key2:
            return dictionary[key1][key2]
        else:
            return dictionary[key1]
    except:
        return None


def check_df_field_value(dataframe, column, row, value):
    """
    Check if the data stored in the dataframe, column key, row rownumber equals
    the target date. Value is compared using the '==' operator
    :param dataframe: The dataframe
    :param column: Name of the column
    :param row: Row number
    :param value: target date
    :return:
    """
    try:
        field_value = str(dataframe[column].iloc[row])
        if field_value == value:
            return True
        else:
            return False
    except:
        return False


def day_present(conn, day):
    """
    Check if specified data is present in the database
    :param conn: Database connection
    :param day: date to check
    :return: True, if date is present
    """
    try:
        day_str = str(day.strftime("%Y-%m-%d"))
        query = "select * from Daily_Summary where Date == '" + day_str + "'"
        df = pd.read_sql(query, conn)
        return not df.empty
    except:
        return False


def get_cache_filename(name, date):
    """
    Determine the filename for caching, including subdirs
    Generic function for the store and retrieve methods to assure
    same filename convention is used.
    Path = Cache/<year>/<date>_<name>.json
    :param name: Filename
    :param date: Date of the data (string, format YYYY-MM-DD)
    :return:
    """
    year_subdir = date[:4]
    fn = os.path.join("Cache", year_subdir, date + "_" + name + ".json")
    return fn


def read_from_cache(name, date):
    """
    Read dictionary from cache
    :param name: type of data
    :param date: date of data to retrieve
    :return: dict with data or None
    """
    if cache_enabled:
        fn = get_cache_filename(name, date)
        if os.path.isfile(fn):
            if DEBUG_CACHE:
                print("Reading from cache : " + fn)
            with open(fn, 'r') as fp:
                data = json.load(fp)
            return data
    return None


def save_to_cache(name, date, data):
    """
    Save data to cache directory
    :param name: type of data
    :param date: date of the data
    :param data: the dict to store
    :return:
    """
    fn = get_cache_filename(name, date)
    if DEBUG_CACHE:
        print("Storing to cache : " + fn)
    with open(fn, 'w') as fp:
        json.dump(data, fp)


def clean_df_from_db_duplicates(df, tablename, engine, dup_cols=[],
                                filter_continuous_col=None, filter_categorical_col=None):
    """
    Remove rows from a dataframe that already exist in a database
    Thank you Ryan Baumann:
    https://www.ryanbaumann.com/blog/2016/4/30/python-pandas-tosql-only-insert-new-rows
    Required:
        df : dataframe to remove duplicate rows from
        engine: SQLAlchemy engine object
        tablename: tablename to check duplicates in
        dup_cols: list or tuple of column names to check for duplicate row values
    Optional:
        filter_continuous_col: the name of the continuous data column for BETWEEEN min/max filter
                               can be either a datetime, int, or float data type
                               useful for restricting the database table size to check
        filter_categorical_col : the name of the categorical data column for Where = value check
                                 Creates an "IN ()" check on the unique values in this column
    Returns
        Unique list of values from dataframe compared to database table
    """
    args = 'SELECT %s FROM %s' % (', '.join(['"{0}"'.format(col) for col in dup_cols]), tablename)
    args_contin_filter, args_cat_filter = None, None
    if filter_continuous_col is not None:
        if df[filter_continuous_col].dtype == 'datetime64[ns]':
            args_contin_filter = """ "%s" BETWEEN Convert(datetime, '%s')
                                          AND Convert(datetime, '%s')""" % (filter_continuous_col,
                                                                            df[filter_continuous_col].min(),
                                                                            df[filter_continuous_col].max())

    if filter_categorical_col is not None:
        args_cat_filter = ' "%s" in(%s)' % (filter_categorical_col,
                                            ', '.join(["'{0}'".format(value) for value in
                                                       df[filter_categorical_col].unique()]))

    if args_contin_filter and args_cat_filter:
        args += ' Where ' + args_contin_filter + ' AND' + args_cat_filter
    elif args_contin_filter:
        args += ' Where ' + args_contin_filter
    elif args_cat_filter:
        args += ' Where ' + args_cat_filter

    df.drop_duplicates(dup_cols, keep='last', inplace=True)

    try:
        df = pd.merge(df, pd.read_sql(args, engine), how='left', on=dup_cols, indicator=True)
        df = df[df['_merge'] == 'left_only']
        df.drop(['_merge'], axis=1, inplace=True)
        return df
    except:
        return df


def save_df(dataframe, logdate, filename, tablename, cnx, dup_cols, save_csv=True, save_sql=True):
    """
    Save a datafram to CSV and SQL
    :param dataframe: Dataframe to save
    :param logdate: Day of logging
    :param filename: Filename (path and prefix) for storage, will be appende with date and ".csv"
    :param tablename: Tablename in the SQLite database
    :param cnx: Connection to the SQLite database
    :param dup_cols: Column names functioning as primary key for duplicate prevetion, e.g. ["Date", "Log"]
    :param save_csv: Specifies if data should be stored in CSV (default TRUE)
    :param save_sql: Specifies if data should be stored in CSV (default FALSE)
    :return:
    """
    if not dataframe is None:
        if save_csv:
            dataframe.to_csv(filename + logdate.replace('-', '') + '.csv', header=True, index=False)
        if save_sql:
            dataframe_new = clean_df_from_db_duplicates(dataframe, tablename, cnx, dup_cols=dup_cols)
            dataframe_new.to_sql(name=tablename, con=cnx, if_exists='append', index=False)


def save_detailed_activities(fb_client, db_conn, day):
    """
    Download and save detailed activity information from Fitbit API
    Stores sleep day overview and summary
    :param fb_client: Fitbit Client
    :param db_conn: DB connection
    :param day: day to retrieve
    :return:
    """
    day_str = str(day.strftime("%Y-%m-%d"))

    for act in ["calories", "steps", "distance", "floors", "elevation", "activityCalories"]:
        act_stats = read_from_cache("activities_" + act, day_str)
        if not act_stats:
            act_stats = fb_client.intraday_time_series('activities/' + act, base_date=day_str, detail_level='1min')
            save_to_cache("activities_" + act, day_str, act_stats, )

    floor_stats = read_from_cache("activities_floors", day_str)
    date_list = []
    time_list = []
    val_list = []
    for i in floor_stats['activities-floors-intraday']['dataset']:
        date_list.append(day_str)
        val_list.append(i['value'])
        time_list.append(i['time'])
    floorsdf = pd.DataFrame({'Date': date_list, 'Time': time_list, 'Floors': val_list})
    save_df(floorsdf, day_str, 'Floors/floors_intraday_', 'Floors_1m', db_conn, ['Date', 'Time'])

    elev_stats = read_from_cache("activities_elevation", day_str)
    date_list = []
    time_list = []
    val_list = []
    for i in elev_stats['activities-elevation-intraday']['dataset']:
        date_list.append(day_str)
        val_list.append(i['value'])
        time_list.append(i['time'])
    elevsdf = pd.DataFrame({'Date': date_list, 'Time': time_list, 'Elevation': val_list})
    save_df(elevsdf, day_str, 'Elevation/elevation_intraday_', 'Elevation_1m', db_conn, ['Date', 'Time'])

    dist_stats = read_from_cache("activities_distance", day_str)
    date_list = []
    time_list = []
    val_list = []
    for i in dist_stats['activities-distance-intraday']['dataset']:
        date_list.append(day_str)
        val_list.append(i['value'])
        time_list.append(i['time'])
    distdf = pd.DataFrame({'Date': date_list, 'Time': time_list, 'Distance': val_list})
    save_df(distdf, day_str, 'Distance/distance_intraday_', 'Distance_1m', db_conn, ['Date', 'Time'])

    cal_stats = read_from_cache("activities_calories", day_str)
    date_list = []
    time_list = []
    val_list = []
    for i in cal_stats['activities-calories-intraday']['dataset']:
        date_list.append(day_str)
        val_list.append(i['value'])
        time_list.append(i['time'])
    caldf = pd.DataFrame({'Date': date_list, 'Time': time_list, 'Calories': val_list})
    save_df(caldf, day_str, 'Calories/calories_intraday_', 'Calories_1m', db_conn, ['Date', 'Time'])


def save_body(fb_client, db_conn, day):
    """
    Download and save body information from Fitbit API
    At this moment, only store to cache
    :param fb_client: Fitbit Client
    :param db_conn: DB connection
    :param day: day to retrieve
    :return:
    """
    day_str = str(day.strftime("%Y-%m-%d"))

    weight_stats = read_from_cache("weight", day_str)
    if not weight_stats:
        weight_stats = fb_client.get_bodyweight(day, period='1d')
        save_to_cache("weight", day_str, weight_stats)

    body_df = pd.DataFrame({
        'Date': get_dict_element(weight_stats, 'weight', 0, 'date'),
        'Weight': get_dict_element(weight_stats, 'weight', 0, 'weight'),
        'Bodyfat': get_dict_element(weight_stats, 'weight', 0, 'fat'),
        'BMI': get_dict_element(weight_stats, 'weight', 0, 'bmi')
    }, index=[0])
    if check_df_field_value(body_df, 'Date', 0, day_str):
        save_df(body_df, day_str, 'Body/body__', 'Body', db_conn, ['Date'])


def save_activities(fb_client, db_conn, day):
    """
    Download and save activity information from Fitbit API
    Stores sleep day overview and summary
    :param fb_client: Fitbit Client
    :param db_conn: DB connection
    :param day: day to retrieve
    :return:
    """
    day_str = str(day.strftime("%Y-%m-%d"))
    url = "https://api.fitbit.com/1/user/-/activities/date/{year}-{month}-{day}.json".format(
        year=day.year,
        month=day.month,
        day=day.day
    )

    act_stats = read_from_cache("activities", day_str)
    if not act_stats:
        act_stats = fb_client.make_request(url)  # dict
        save_to_cache("activities", day_str, act_stats)

    log_activities = pd.DataFrame({
        'Date': day_str,
        'Goal Active Minutes': get_dict_element(act_stats, 'goals', 'activeMinutes'),
        'Goal Calories Out': get_dict_element(act_stats, 'goals', 'caloriesOut'),
        'Goal Distance': get_dict_element(act_stats, 'goals', 'distance'),
        'Goal Floors': get_dict_element(act_stats, 'goals', 'floors'),
        'Goal Steps': get_dict_element(act_stats, 'goals', 'steps'),
        'Active Score': act_stats['summary']['activeScore'],
        'Steps': act_stats['summary']['steps'],
        'Distance': act_stats['summary']['distances'][0]['distance'],
        'Elevation': act_stats['summary']['elevation'],
        'Floors': act_stats['summary']['floors'],
        'Resting Heart Rate': get_dict_element(act_stats, 'summary', 'restingHeartRate'),
        'Activity Calories': act_stats['summary']['activityCalories'],
        'Calories BMR': act_stats['summary']['caloriesBMR'],
        'Marginal Calories': act_stats['summary']['marginalCalories'],
        'Calories Out': act_stats['summary']['caloriesOut'],
        'Sedentary Minutes': act_stats['summary']['sedentaryMinutes'],
        'Lightly Active Minutes': act_stats['summary']['lightlyActiveMinutes'],
        'Fairly Active Minutes': act_stats['summary']['fairlyActiveMinutes'],
        'Very Active Minutes': act_stats['summary']['veryActiveMinutes']
    }, index=[0])

    save_df(log_activities, day_str, 'Activities/activities_summary_', 'Activities_Summary', db_conn, ['Date'])

    desc_list = []
    val_list = []
    date_list = []
    for rec in act_stats['summary']['distances']:
        date_list.append(day_str)
        desc_list.append(rec['activity'])
        val_list.append(rec['distance'])
    dist_df = pd.DataFrame({'Date': date_list, 'Activity': desc_list, 'Distance': val_list})
    save_df(dist_df, day_str, 'Activities/distance_', 'Distance', db_conn, ['Date', 'Activity'])

    desc_list = []
    val_list = []
    date_list = []
    id_list = []
    min_list = []
    max_list = []
    cal_list = []
    i = 0
    for rec in act_stats['summary']['heartRateZones']:
        date_list.append(day_str)
        id_list.append(i)
        desc_list.append(rec['name'])
        val_list.append(rec['minutes'])
        min_list.append(rec['min'])
        max_list.append(rec['max'])
        cal_list.append(rec['caloriesOut'])
        i = i + 1
    hr_df = pd.DataFrame({'Date': date_list, 'Name': desc_list, 'ID': id_list, 'Minutes': min_list,
                          'Calories': cal_list, 'Min': min_list, 'Max': max_list})

    save_df(hr_df, day_str, 'Activities/hr_zones_', 'HeartRate_Zones', db_conn, ['Date', 'Name'])


def save_training(fb_client, db_conn, day):
    """
    Download and save training activitites from Fitbit API
    Stores sleep day overview and summary
    :param fb_client: Fitbit Client
    :param db_conn: DB connection
    :param day: day to retrieve
    :return:
    """
    day_str = str(day.strftime("%Y-%m-%d"))
    day_after = day + datetime.timedelta(days=1)
    day_after_str = str(day_after.strftime("%Y-%m-%d"))

    training_stats = read_from_cache("training", day_str)
    if not training_stats:
        url = "https://api.fitbit.com/1/user/-/activities/list.json?beforeDate=" + \
              day_after_str + "&sort=desc&offset=0&limit=10"
        training_stats = fb_client.make_request(url)  # dict
        save_to_cache("training", day_str, training_stats)

    for act in training_stats['activities']:
        start_time = act['startTime'][:26] + act['startTime'][27:]  # Remove : from timezone
        if start_time[:10] == day_str:
            train_df = pd.DataFrame({
                'Date': day_str,
                'ID': get_dict_element(act, 'logId'),
                'Start': start_time,
                'Type': get_dict_element(act, 'activityName'),
                'Duration': get_dict_element(act, 'duration'),
                'Steps': get_dict_element(act, 'steps'),
                'AverageHeartRate': get_dict_element(act, 'averageHeartRate'),
                'Calories': get_dict_element(act, 'calories'),
                'ElevationGain': get_dict_element(act, 'elevationGain'),
                'HeartRateZone0': get_dict_element(act, 'heartRateZones', 0, 'minutes'),
                'HeartRateZone1': get_dict_element(act, 'heartRateZones', 1, 'minutes'),
                'HeartRateZone2': get_dict_element(act, 'heartRateZones', 2, 'minutes'),
                'HeartRateZone3': get_dict_element(act, 'heartRateZones', 3, 'minutes'),
                'ActiveDuration': get_dict_element(act, 'activeDuration'),
                'ActivityLevel0': get_dict_element(act, 'activityLevel', 0, 'minutes'),
                'ActivityLevel1': get_dict_element(act, 'activityLevel', 1, 'minutes'),
                'ActivityLevel2': get_dict_element(act, 'activityLevel', 2, 'minutes'),
                'ActivityLevel3': get_dict_element(act, 'activityLevel', 3, 'minutes'),
            }, index=[0])
            save_df(train_df, day_str, 'Training/training_', 'Training', db_conn, ['ID'])


def save_sleep(fb_client, db_conn, day):
    """
    Download and save sleep from Fitbit API
    Stores sleep day overview and summary
    :param fb_client: Fitbit Client
    :param db_conn: DB connection
    :param day: day to retrieve
    :return:
    """
    day_str = str(day.strftime("%Y-%m-%d"))

    sleep_stats = read_from_cache("sleep", day_str)
    if not sleep_stats:
        sleep_stats = fb_client.get_sleep(day)
        save_to_cache("sleep", day_str, sleep_stats)

    log_stats = None
    i = 0
    for rec in sleep_stats['sleep']:
        log_stats2 = pd.DataFrame({
            'Date': rec['dateOfSleep'],
            'Log Count': i,
            'Start Time': rec['startTime'],
            'End Time': rec['endTime'],
            'Time In Bed': rec['timeInBed'],
            'Awake Count': rec['awakeCount'],
            'Awake Duration': rec['awakeDuration'],
            'Awakenings Count': rec['awakeningsCount'],
            'Duration': rec['duration'],
            'Efficiency': rec['efficiency'],
            'Main Sleep': rec['isMainSleep'],
            'Log ID': rec['logId'],
            'Minutes After Wakeup': rec['minutesAfterWakeup'],
            'Minutes Asleep': rec['minutesAsleep'],
            'Minutes Awake': rec['minutesAwake'],
            'Minutes To Fall Asleep': rec['minutesToFallAsleep'],
            'Restless Count': rec['restlessCount'],
            'Restless Duration': rec['restlessDuration']
        }, index=[0])
        if i > 0:
            log_stats.append(log_stats2)
        else:
            log_stats = log_stats2.copy()
        i = i + 1
    save_df(log_stats, day_str, 'Sleep/sleep_statistics_', 'Sleep', db_conn, ['Date', 'Log Count'])

    # check if stages are present
    summary = pd.DataFrame({
        'Date': get_dict_element(sleep_stats, 'sleep', 0, 'dateOfSleep'),
        'Minutes Asleep': get_dict_element(sleep_stats, 'summary', 'totalMinutesAsleep'),
        'Sleep Records': get_dict_element(sleep_stats, 'summary', 'totalSleepRecords'),
        'Time in Bed': get_dict_element(sleep_stats, 'summary', 'totalTimeInBed'),
        'Stage Deep': get_dict_element(sleep_stats, 'summary', 'stages', 'deep'),
        'Stage Light': get_dict_element(sleep_stats, 'summary', 'stages', 'light'),
        'Stage REM': get_dict_element(sleep_stats, 'summary', 'stages', 'rem'),
        'Stage Wake': get_dict_element(sleep_stats, 'summary', 'stages', 'wake')
    }, index=[0])
    save_df(summary, day_str, 'Sleep/sleep_summary_', 'Sleep_Summary', db_conn, ['Date'])

    time_list = []
    val_list = []
    date_list = []
    logid_list = []
    for sleep_log in sleep_stats['sleep']:
        logid = sleep_log['logId']
        for i in sleep_log['minuteData']:
            date_list.append(day_str)
            logid_list.append(logid)
            val_list.append(i['value'])
            time_list.append(i['dateTime'])
    sleepmin_df = pd.DataFrame({'Date': date_list, 'LogID': logid_list, 'Time': time_list, 'Value': val_list})
    sleepmin_df['interpreted'] = sleepmin_df['Value'].map({'2': 'Restless', '3': 'Awake', '1': 'Asleep'})
    save_df(sleepmin_df, day_str, 'Sleep/sleep_minlog_', 'Sleep_1m', db_conn, ['Date', 'LogID', 'Time'])


def save_steps(fb_client, db_conn, day):
    """
    Download and save steps from Fitbit API
    Stores intraday steps, granularity 1 min and day summary
    :param fb_client: Fitbit Client
    :param db_conn: DB connection
    :param day: day to retrieve
    :return:
    """
    day_str = str(day.strftime("%Y-%m-%d"))

    step_stats = read_from_cache("steps_1m", day_str)
    if not step_stats:
        step_stats = fb_client.intraday_time_series('activities/steps', base_date=day_str, detail_level='1min')
        save_to_cache("steps_1m", day_str, step_stats)

    date_list = []
    time_list = []
    val_list = []
    for i in step_stats['activities-steps-intraday']['dataset']:
        date_list.append(day_str)
        val_list.append(i['value'])
        time_list.append(i['time'])
    stepsdf = pd.DataFrame({'Date': date_list, 'Time': time_list, 'Steps': val_list})
    save_df(stepsdf, day_str, 'Steps/steps_intraday_', 'Steps_1m', db_conn, ['Date', 'Time'])

    summary = pd.DataFrame({
        'Date': step_stats['activities-steps'][0]['dateTime'],
        'Steps': step_stats['activities-steps'][0]['value']
        }, index=[0])
    save_df(summary, day_str, 'Steps/steps_daysummary_', 'Steps_Summary', db_conn, ['Date'])


def save_heart(fb_client, db_conn, day):
    day_str = str(day.strftime("%Y-%m-%d"))

    hr_stats = read_from_cache("heart_1m", day_str)
    if not hr_stats:
        hr_stats = fb_client.intraday_time_series('activities/heart', base_date=day_str, detail_level='1min')
        save_to_cache("heart_1m", day_str, hr_stats)

    time_list = []
    val_list = []
    date_list = []
    for i in hr_stats['activities-heart-intraday']['dataset']:
        date_list.append(day_str)
        val_list.append(i['value'])
        time_list.append(i['time'])
    heartdf = pd.DataFrame({'Date': date_list, 'Time': time_list, 'Heart Rate': val_list})
    save_df(heartdf, day_str, 'Heart/heart_intraday_', 'Heartrate', db_conn, ['Date', 'Time'])

    summary = pd.DataFrame({
        'Date': hr_stats['activities-heart'][0]['dateTime'],
        'Resting Heart Rate': get_dict_element(hr_stats['activities-heart'][0]['value'], ['restingHeartRate']),

        'Zone0 Calories': hr_stats['activities-heart'][0]['value']['heartRateZones'][0]['caloriesOut'],
        'Zone0 Mxax': hr_stats['activities-heart'][0]['value']['heartRateZones'][0]['max'],
        'Zone0 Min': hr_stats['activities-heart'][0]['value']['heartRateZones'][0]['min'],
        'Zone0 Minutes': hr_stats['activities-heart'][0]['value']['heartRateZones'][0]['minutes'],
        'Zone0  Name': hr_stats['activities-heart'][0]['value']['heartRateZones'][0]['name'],

        'Zone1 Calories': hr_stats['activities-heart'][0]['value']['heartRateZones'][1]['caloriesOut'],
        'Zone1 Max': hr_stats['activities-heart'][0]['value']['heartRateZones'][1]['max'],
        'Zone1 Min': hr_stats['activities-heart'][0]['value']['heartRateZones'][1]['min'],
        'Zone1 Minutes': hr_stats['activities-heart'][0]['value']['heartRateZones'][1]['minutes'],
        'Zone1 Name': hr_stats['activities-heart'][0]['value']['heartRateZones'][1]['name'],

        'Zone2 Calories': hr_stats['activities-heart'][0]['value']['heartRateZones'][2]['caloriesOut'],
        'Zone2 Max': hr_stats['activities-heart'][0]['value']['heartRateZones'][2]['max'],
        'Zone2 Min': hr_stats['activities-heart'][0]['value']['heartRateZones'][2]['min'],
        'Zone2 Minutes': hr_stats['activities-heart'][0]['value']['heartRateZones'][2]['minutes'],
        'Zone2 Name': hr_stats['activities-heart'][0]['value']['heartRateZones'][2]['name'],

        'Zone3 Calories': hr_stats['activities-heart'][0]['value']['heartRateZones'][3]['caloriesOut'],
        'Zone3 Max': hr_stats['activities-heart'][0]['value']['heartRateZones'][3]['max'],
        'Zone3 Min': hr_stats['activities-heart'][0]['value']['heartRateZones'][3]['min'],
        'Zone3 Minutes': hr_stats['activities-heart'][0]['value']['heartRateZones'][3]['minutes'],
        'Zone3 Name': hr_stats['activities-heart'][0]['value']['heartRateZones'][3]['name']
    }, index=[0])

    save_df(summary, day_str, 'Heart/heart_daysummary_', 'Heartrate_Summary', db_conn, ['Date'])


def create_daily_summary(day, db_conn):
    """
    Create a daily summary in the corresponding table
    Assumption: all data available in the cache
    :param day: day to summarize
    :param db_conn: Database connection for storing result
    :return:
    """

    # Load data from cache (sleep and activitites
    day_str = str(day.strftime("%Y-%m-%d"))
    act_stats = read_from_cache("activities", day_str)
    sleep_stats = read_from_cache("sleep", day_str)
    hr_stats = read_from_cache("heart_1m", day_str)

    # Check if data present
    if not act_stats:
        return

    # Find main sleep
    mainsleep_stats = None
    for rec2 in sleep_stats['sleep']:
        if rec2['isMainSleep']:
            mainsleep_stats = rec2

    # Create summary dataframe
    summary = pd.DataFrame({
        'Date': day_str,

        'Goal Active Minutes': get_dict_element(act_stats, 'goals', 'activeMinutes'),
        'Goal Calories Out': get_dict_element(act_stats, 'goals', 'caloriesOut'),
        'Goal Distance': get_dict_element(act_stats, 'goals', 'distance'),
        'Goal Floors': get_dict_element(act_stats, 'goals', 'floors'),
        'Goal Steps': get_dict_element(act_stats, 'goals', 'steps'),

        'Active Score': act_stats['summary']['activeScore'],
        'Steps': act_stats['summary']['steps'],
        'Distance': act_stats['summary']['distances'][0]['distance'],
        'Elevation': act_stats['summary']['elevation'],
        'Floors': act_stats['summary']['floors'],

        'Resting Heart Rate': get_dict_element(act_stats, 'summary', 'restingHeartRate'),

        'Activity Calories': act_stats['summary']['activityCalories'],
        'Calories BMR': act_stats['summary']['caloriesBMR'],
        'Marginal Calories': act_stats['summary']['marginalCalories'],
        'Calories Out': act_stats['summary']['caloriesOut'],
        'Sedentary Minutes': act_stats['summary']['sedentaryMinutes'],
        'Lightly Active Minutes': act_stats['summary']['lightlyActiveMinutes'],
        'Fairly Active Minutes': act_stats['summary']['fairlyActiveMinutes'],
        'Very Active Minutes': act_stats['summary']['veryActiveMinutes'],

        'Minutes Asleep': get_dict_element(sleep_stats, 'summary', 'totalMinutesAsleep'),
        'Sleep Records': get_dict_element(sleep_stats, 'summary', 'totalSleepRecords'),
        'Time in Bed': get_dict_element(sleep_stats, 'summary', 'totalTimeInBed'),
        'Stage Deep': get_dict_element(sleep_stats, 'summary', 'stages', 'deep'),
        'Stage Light': get_dict_element(sleep_stats, 'summary', 'stages', 'light'),
        'Stage REM': get_dict_element(sleep_stats, 'summary', 'stages', 'rem'),
        'Stage Wake': get_dict_element(sleep_stats, 'summary', 'stages', 'wake'),

        'Zone0 Calories': hr_stats['activities-heart'][0]['value']['heartRateZones'][0]['caloriesOut'],
        'Zone0 Mxax': hr_stats['activities-heart'][0]['value']['heartRateZones'][0]['max'],
        'Zone0 Min': hr_stats['activities-heart'][0]['value']['heartRateZones'][0]['min'],
        'Zone0 Minutes': hr_stats['activities-heart'][0]['value']['heartRateZones'][0]['minutes'],
        'Zone0  Name': hr_stats['activities-heart'][0]['value']['heartRateZones'][0]['name'],

        'Zone1 Calories': hr_stats['activities-heart'][0]['value']['heartRateZones'][1]['caloriesOut'],
        'Zone1 Max': hr_stats['activities-heart'][0]['value']['heartRateZones'][1]['max'],
        'Zone1 Min': hr_stats['activities-heart'][0]['value']['heartRateZones'][1]['min'],
        'Zone1 Minutes': hr_stats['activities-heart'][0]['value']['heartRateZones'][1]['minutes'],
        'Zone1 Name': hr_stats['activities-heart'][0]['value']['heartRateZones'][1]['name'],

        'Zone2 Calories': hr_stats['activities-heart'][0]['value']['heartRateZones'][2]['caloriesOut'],
        'Zone2 Max': hr_stats['activities-heart'][0]['value']['heartRateZones'][2]['max'],
        'Zone2 Min': hr_stats['activities-heart'][0]['value']['heartRateZones'][2]['min'],
        'Zone2 Minutes': hr_stats['activities-heart'][0]['value']['heartRateZones'][2]['minutes'],
        'Zone2 Name': hr_stats['activities-heart'][0]['value']['heartRateZones'][2]['name'],

        'Zone3 Calories': hr_stats['activities-heart'][0]['value']['heartRateZones'][3]['caloriesOut'],
        'Zone3 Max': hr_stats['activities-heart'][0]['value']['heartRateZones'][3]['max'],
        'Zone3 Min': hr_stats['activities-heart'][0]['value']['heartRateZones'][3]['min'],
        'Zone3 Minutes': hr_stats['activities-heart'][0]['value']['heartRateZones'][3]['minutes'],
        'Zone3 Name': hr_stats['activities-heart'][0]['value']['heartRateZones'][3]['name'],

        'Sleep Start Time': get_dict_element(mainsleep_stats, 'startTime'),
        'Sleep End Time': get_dict_element(mainsleep_stats, 'endTime'),
        'Sleep Time In Bed': get_dict_element(mainsleep_stats, 'timeInBed'),
        'Sleep Awake Count': get_dict_element(mainsleep_stats, 'awakeCount'),
        'Sleep Awake Duration': get_dict_element(mainsleep_stats, 'awakeDuration'),
        'Sleep Awakenings Count': get_dict_element(mainsleep_stats, 'awakeningsCount'),
        'Sleep Duration': get_dict_element(mainsleep_stats, 'duration'),
        'Sleep Efficiency': get_dict_element(mainsleep_stats, 'efficiency'),
        'Sleep Minutes After Wakeup': get_dict_element(mainsleep_stats, 'minutesAfterWakeup'),
        'Sleep Minutes Asleep': get_dict_element(mainsleep_stats, 'minutesAsleep'),
        'Sleep Minutes Awake': get_dict_element(mainsleep_stats, 'minutesAwake'),
        'Sleep Minutes To Fall Asleep': get_dict_element(mainsleep_stats, 'minutesToFallAsleep'),
        'Sleep Restless Count': get_dict_element(mainsleep_stats, 'restlessCount'),
        'Sleep Restless Duration': get_dict_element(mainsleep_stats, 'restlessDuration')

    }, index=[0])
    #
    # Add main sleep
    #
    save_df(summary, day_str, 'Daily/daily_summary_', 'Daily_Summary', db_conn, ['Date'])


def get_fitbit_client(fb_id, fb_secret):
    server = Oauth2.OAuth2Server(fb_id, fb_secret)
    server.browser_authorize()
    access_token = str(server.fitbit.client.session.token['access_token'])
    refresh_token = str(server.fitbit.client.session.token['refresh_token'])
    client = fitbit.Fitbit(fb_id, fb_secret, oauth2=True, access_token=access_token,
                           refresh_token=refresh_token, system="en_UK")
    # Keep cherry webserver log and app log seperated
    time.sleep(1)
    return client


def save_fitbit_data(fitbit_client, database_connection, day):
    """
    Download and save the fitbit data for a specific day
    :param fitbit_client: Fitbit API Client
    :param database_connection: Connection to the database
    :param day: day to retrieve (type: Datetime object)
    :return:
    """
    save_detailed_activities(fitbit_client, database_connection, day)
    save_body(fitbit_client, database_connection, day)
    save_sleep(fitbit_client, database_connection, day)
    save_activities(fitbit_client, database_connection, day)
    save_steps(fitbit_client, database_connection, day)
    save_training(fitbit_client, database_connection, day)
    save_heart(fitbit_client, database_connection, day)


def get_arguments():
    """
    Handle application arguments
    :return: arguments object
    """
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description='Fitbit Scraper')
    parser.add_argument('--id', metavar='clientId', dest='clientId', required=True,
                        help="client-id of your Fitbit app")
    parser.add_argument('--secret', metavar='clientSecret', dest='clientSecret', required=True,
                        help="client-secret of your Fitbit app")
    parser.add_argument('--first', dest='firstDate', default="2017-09-24",
                        help="Date (YYYY-MM-DD) of oldest Fitbit data")
    parser.add_argument('--start', dest='startDate', default=yesterday,
                        help="Date (YYYY-MM-DD) from which to start the backward scraping. Default is today")
    parser.add_argument('--limit', type=int, dest='limit', default=7,
                        help="maximum number of days to download. Default is 7")
    parser.add_argument('--online', dest='online', action='store_true')
    parser.add_argument('--offline', dest='online', action='store_false')
    parser.set_defaults(online=True)
    parser.add_argument('--no-cache', dest='cache', action='store_false',
                        help='Do not use cached results but always download all data (cache is still updated')
    parser.set_defaults(cache=True)
    return parser.parse_args()


if __name__ == "__main__":

    # Parse and handle application arguments
    arguments = get_arguments()
    FB_ID = arguments.clientId
    FB_SECRET = arguments.clientSecret
    start_date = datetime.datetime.strptime(arguments.startDate, "%Y-%m-%d").date()
    first_date_of_data = datetime.datetime.strptime(arguments.firstDate, "%Y-%m-%d").date()
    limit = arguments.limit
    online = arguments.online
    cache_enabled = arguments.cache

    # Assure directories are present to store the data
    create_directories()

    # Get a Fitbit client, but only if onlie is enabled
    if online:
        auth2_client = get_fitbit_client(FB_ID, FB_SECRET)
    else:
        auth2_client = None

    # Shoe download configuration
    print("Configuration")
    print("------------------------------------------------")
    print("Fitbit ID        : " + FB_ID)
    print("Fitbit Secret    : " + FB_SECRET)
    print("Oldest available : " + first_date_of_data.strftime("%Y-%m-%d"))
    print("Online           : " + str(online))
    print("Cache            : " + str(cache_enabled))
    print("Start date       : " + start_date.strftime("%Y-%m-%d"))
    print("Day limit        : " + str(limit))
    print("------------------------------------------------")

    for j in range(0, limit):
        # Open database connection per data
        # Prevents accidental data loss
        db_connection = sqlite3.connect('data/fitbit.db')
        day_to_retrieve = start_date - datetime.timedelta(days=j)

        # Retry a date if the fitbit max request error occurs
        day_handled = False
        while not day_handled:
            try:
                # Only retrieve if there is data for this date
                # Prevents reading before the data Fitbit data is available
                # If summary record ia available, do not read
                # if True:
                if day_to_retrieve >= first_date_of_data and not day_present(db_connection, day_to_retrieve):
                    print("Downloading day {} : {}".format(j, day_to_retrieve.strftime("%Y-%m-%d")))
                    save_fitbit_data(auth2_client, db_connection, day_to_retrieve)
                    create_daily_summary(day_to_retrieve, db_connection)
                else:
                    print("Skipping day {} : {}".format(j, day_to_retrieve.strftime("%Y-%m-%d")))
                # Retrievel is succesfull so continu to next day
                day_handled = True

            except fitbit.exceptions.HTTPTooManyRequests:
                # Too many request to the Fitbit API, sleep and retry
                print("Too many request, time to sleep")
                time.sleep(300)

            # except ???:
            #     # access token no longer valid. Retrieve new token
            #     # and retry download
            #     auth2_client = get_fitbit_client(FB_ID, FB_SECRET)

            except Exception as e:
                # Unexpected error. Print the error and exit the application
                # Detailed error information is printed to ease problem solving
                print("Exception : " + str(e))
                traceback.print_exc()
                print("")
                error = traceback.format_exc()
                print(error.upper())
                print("Goodbye!")
                exit()
            finally:
                # Close database connection and commit changes
                db_connection.commit()

    db_connection.close()