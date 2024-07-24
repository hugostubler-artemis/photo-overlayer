import pandas as pd
from datetime import datetime, timezone
import numpy as np
import pytz
import streamlit as st
import os
from influxdb_client import InfluxDBClient
import sys
from datetime import datetime, timedelta

#from HelperFunctions.InfluxDbTimeFunctions import TimeToInfluxEpoch_s

#from HelperFunctions.utils import *
# InfluxDB setting
INFLUXDB_API_URL = "https://influxdb.artemisracing.com"
INFLUXDB_ORGANISATION = "ArtemisRacing"

INFLUXDB_TOKEN = "Q0Q77KR-MasuFGIJGapH5EvXhCMHd_fE4GssuJWog0FlYP6MJU3zgjXYjL7Vd9aibEPRqY-KXGkYfK6sEtaCdw=="  # token for AC40
INFLUXDB_BUCKET = "AC40"

INFLUXDB_MAX_POINTS_BULK_UPLOAD = 5000


def stringToDate(input_string:str)->datetime:
    # Convert the input string to a datetime object
    if isinstance(input_string, datetime):
        return input_string
    
    has_ms:bool="." in input_string
    if "T" in input_string or "Z" in input_string:
        if has_ms:
            return datetime.strptime(input_string, '%Y-%m-%dT%H:%M:%S.%fZ')
        return datetime.strptime(input_string, '%Y-%m-%dT%H:%M:%SZ')
    else:
        if has_ms:
            return datetime.strptime(input_string, '%Y-%m-%d %H:%M:%S.%f')
        return datetime.strptime(input_string, '%Y-%m-%d %H:%M:%S')

def TimeToInfluxEpoch_ns(dt):
    dt0 = datetime.fromtimestamp(   0, tz= timezone.utc)
    delta = (dt - dt0) 
    return int(delta.total_seconds() * 1000 *1000000)

def TimeToInfluxEpoch_ms(dt:datetime)->int:
    epoch = datetime(1970, 1, 1)
    dt=stringToDate(dt)
    delta = dt - epoch
    return int(delta.total_seconds() * 1000)

def TimeToInfluxEpoch_s(dt):
    dt0 = datetime.fromtimestamp(0, tz=pytz.UTC)
    dt1 = dt.astimezone(pytz.UTC)  # Convert dt to UTC timezone
    delta = dt1 - dt0
    return int(delta.total_seconds())

def InfluxEpochToTime(epoch):
    dt0 = datetime.fromtimestamp(   0, tz= timezone.utc) #datetime.strptime("1970-01-01 00:00:00.0", "%Y-%m-%d %H:%M:%S.%f")
    return dt0 + timedelta(milliseconds= (epoch / 1000000))


def QueryInfluxData(
        bucket, varMapping, fromTime, toTime, freq="1s", whereTags=None) -> pd.DataFrame:

    st.write("Connecting to influx database '", bucket, "'...")

    # open conx to InfluxDB
    #st.write("Connecting to influx...")
    try:
        influx_client = InfluxDBClient(
            url=INFLUXDB_API_URL,
            token=INFLUXDB_TOKEN,
            org=INFLUXDB_ORGANISATION,
            timeout=30_000,
        )
        influx_query_api = influx_client.query_api()
    except Exception as e:
        st.write("ERROR: ", e)
        return
    #st.success("Done.")

    df = pd.DataFrame()
    # Construct the Flux query for each variable
    st.write(f"Querying...")
    for var in varMapping['VarName']:
        
        query: str = f'''
            from(bucket: "{bucket}")\n
            |> range(start: {fromTime.strftime('%Y-%m-%dT%H:%M:%SZ')}, stop: {toTime.strftime('%Y-%m-%dT%H:%M:%SZ')})\n
            |> aggregateWindow(every: {freq}, fn: mean, createEmpty: false)
            |> filter(fn: (r) => r["_measurement"] == "{var}")\n
            |> filter(fn: (r) => r["_field"] == "value")\n
            |> keep(columns: ["_time", "_value"])
        '''
        tables = influx_query_api.query(query)

        # Convert the result to a DataFrame
        records = []
        for table in tables:
            for record in table.records:
                records.append((record.get_time(), record.get_value()))
        df_tmp = pd.DataFrame(records, columns=['_time', var])
        df_tmp['_time'] = pd.to_datetime(df_tmp['_time'])
        df_tmp.set_index('_time', inplace=True)
        df_tmp.index = df_tmp.index.tz_localize(None)

        # Merge the current DataFrame with the combined DataFrame
        if df.empty:
            df = df_tmp
        else:
            df = df.join(df_tmp, how='outer')

        
    df.index = df.index.strftime('%Y-%m-%d %H:%M:%S')
    #st.write(df)
    st.success("data uploaded.")
    df['Datetime'] = df.index
    df['VMG%'] = df.VMG/df.Tgt_VMG
    df['BSP%'] = df.BSP/df.Tgt_BSP
    df.Datetime = pd.to_datetime(df.Datetime)
    df["Link_angle"] = df.Traveller_angle - df.MastRotation_angle
    return df
