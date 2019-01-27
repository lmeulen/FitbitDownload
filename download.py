import fitbit
import gather_keys_oauth2 as Oauth2
import pandas as pd
import datetime
import sqlite3
import os
import json
import argparse
import time


def create_directory_if_not_exist(directory):
    """
    Create directory if it does not exist
    :param directory: name of directory to create
    :return:
    """
    if not os.path.exists(directory):
        os.makedirs(directory)


def read_from_cache(name, date):
    """
    Read dictionary from cache
    :param name: type of data
    :param date: date of data to retrieve
    :return: dict with data or None
    """
    fn = os.path.join("Cache", date + "_" + name + ".json")
    if os.path.isfile(fn):
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
    fn = os.path.join("Cache", date + "_" + name + ".json")
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
    if save_csv:
        dataframe.to_csv(filename + logdate.replace('-', '') + '.csv', header=True, index=False)
    if save_sql:
        dataframe_new = clean_df_from_db_duplicates(dataframe, tablename, cnx, dup_cols=dup_cols)
        dataframe_new.to_sql(name=tablename, con=cnx, if_exists='append', index=False)


def save_detailed_activities(fb_client, db_conn, day):
    """
    Download and save detailed activity information from Fitbit API
    At this moment, only store to cache
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

    fat_stats = read_from_cache("bodyfat", day_str)
    if not fat_stats:
        fat_stats = fb_client.get_bodyfat(day, period='1d')
        save_to_cache("bodyfat", day_str, fat_stats)


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

    if act_stats.get('goals'):
        log_activities = pd.DataFrame({
            'Date': day_str,
            'Goal Active Minutes': act_stats['goals']['activeMinutes'],
            'Goal Calories Out': act_stats['goals']['caloriesOut'],
            'Goal Distance': act_stats['goals']['distance'],
            'Goal Floors': act_stats['goals']['floors'],
            'Goal Steps': act_stats['goals']['steps'],
            'Active Score': act_stats['summary']['activeScore'],
            'Steps': act_stats['summary']['steps'],
            'Distance': act_stats['summary']['distances'][0]['distance'],
            'Elevation': act_stats['summary']['elevation'],
            'Floors': act_stats['summary']['floors'],
            'Resting Heart Rate': act_stats['summary']['restingHeartRate'],
            'Activity Calories': act_stats['summary']['activityCalories'],
            'Calories BMR': act_stats['summary']['caloriesBMR'],
            'Marginal Calories': act_stats['summary']['marginalCalories'],
            'Calories Out': act_stats['summary']['caloriesOut'],
            'Sedentary Minutes': act_stats['summary']['sedentaryMinutes'],
            'Lightly Active Minutes': act_stats['summary']['lightlyActiveMinutes'],
            'Fairly Active Minutes': act_stats['summary']['fairlyActiveMinutes'],
            'Very Active Minutes': act_stats['summary']['veryActiveMinutes']
        }, index=[0])
    else:
        log_activities = pd.DataFrame({
            'Date': day_str,
            'Goal Active Minutes': None,
            'Goal Calories Out': None,
            'Goal Distance': None,
            'Goal Floors': None,
            'Goal Steps': None,
            'Active Score': act_stats['summary']['activeScore'],
            'Steps': act_stats['summary']['steps'],
            'Distance': act_stats['summary']['distances'][0]['distance'],
            'Elevation': act_stats['summary']['elevation'],
            'Floors': act_stats['summary']['floors'],
            'Resting Heart Rate': act_stats['summary']['restingHeartRate'],
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
    if sleep_stats.get('summary').get('stages'):
        summary = pd.DataFrame({
            'Date': sleep_stats['sleep'][0]['dateOfSleep'],
            'Minutes Asleep': sleep_stats['summary']['totalMinutesAsleep'],
            'Sleep Records': sleep_stats['summary']['totalSleepRecords'],
            'Time in Bed': sleep_stats['summary']['totalTimeInBed'],
            'Stage Deep': sleep_stats['summary']['stages']['deep'],
            'Stage Light': sleep_stats['summary']['stages']['light'],
            'Stage REM': sleep_stats['summary']['stages']['rem'],
            'Stage Wake': sleep_stats['summary']['stages']['wake']
        }, index=[0])
    else:
        summary = pd.DataFrame({
            'Date': sleep_stats['sleep'][0]['dateOfSleep'],
            'Minutes Asleep': sleep_stats['summary']['totalMinutesAsleep'],
            'Sleep Records': sleep_stats['summary']['totalSleepRecords'],
            'Time in Bed': sleep_stats['summary']['totalTimeInBed'],
            'Stage Deep': -1,
            'Stage Light': -1,
            'Stage REM': -1,
            'Stage Wake': -1
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
    save_df(sleepmin_df, day_str, 'Sleep/sleep_minlog_', 'Sleep_Min_Log', db_conn, ['Date', 'LogID', 'Time'])


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
    save_df(stepsdf, day_str, 'Steps/steps_intraday_', 'Steps', db_conn, ['Date', 'Time'])

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
        'Resting Heart Rate': hr_stats['activities-heart'][0]['value']['restingHeartRate'],

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


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Fitbit Scraper')
    parser.add_argument('--id', metavar='clientId', dest='clientId', required=True,
                        help="client-id of your Fitbit app")
    parser.add_argument('--secret', metavar='clientSecret', dest='clientSecret', required=True,
                        help="client-secret of your Fitbit app")
    parser.add_argument('--start', dest='startDate', default=datetime.datetime.now().strftime("%Y-%m-%d"),
                        help="Date (YYYY-MM-DD) from which to start the backward scraping. Default is today")
    parser.add_argument('--limit', type=int, dest='limit', default=25,
                        help="maximum number of days to download. Default is 25")
    parser.add_argument('--online', dest='online', action='store_true')
    parser.add_argument('--offline', dest='online', action='store_false')
    parser.set_defaults(online=True)

    arguments = parser.parse_args()
    FB_ID = arguments.clientId
    FB_SECRET = arguments.clientSecret
    startdate = datetime.datetime.strptime(arguments.startDate, "%Y-%m-%d").date()
    limit = arguments.limit
    online = arguments.online
    print("Online : " + str(online))

    print("Starting : {}, maximum days : {}".format(startdate.strftime("%Y-%m-%d"), limit))

    data_directories = ["Sleep", "Steps", "Floors", "Calories", "Distance", "Heart", "Activities", "Data", "Cache"]
    for dir_name in data_directories:
        create_directory_if_not_exist(dir_name)

    if online:
        server = Oauth2.OAuth2Server(FB_ID, FB_SECRET)
        server.browser_authorize()

        ACCESS_TOKEN = str(server.fitbit.client.session.token['access_token'])
        REFRESH_TOKEN = str(server.fitbit.client.session.token['refresh_token'])

        auth2_client = fitbit.Fitbit(FB_ID, FB_SECRET, oauth2=True, access_token=ACCESS_TOKEN,
                                     refresh_token=REFRESH_TOKEN)
        time.sleep(1) # Keep cherry webserver log and app log seperated
    else:
        auth2_client = None


    while True:
        for j in range(0, limit):
            db_connection = sqlite3.connect('data/fitbit.db')
            day_to_retrieve = startdate - datetime.timedelta(days=j)
            print("{} : {}".format(j, day_to_retrieve.strftime("%Y-%m-%d")))
            try:
                save_detailed_activities(auth2_client, db_connection, day_to_retrieve)
                save_body(auth2_client, db_connection, day_to_retrieve)
                save_sleep(auth2_client, db_connection, day_to_retrieve)
                save_activities(auth2_client, db_connection, day_to_retrieve)
                save_steps(auth2_client, db_connection, day_to_retrieve)
                save_heart(auth2_client, db_connection, day_to_retrieve)
            except Exception as e:
                print("Exception : " + str(e))
                print("Time to sleep")
                time.sleep(3600)
            finally:
                db_connection.commit()
