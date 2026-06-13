import pandas as pd
import numpy as np
from datetime import datetime

def parse_sbb_datetime(dt_str):
    """
    Parses SBB date strings into datetime objects.
    Handles formats like 'DD.MM.YYYY HH:MM:SS', 'DD.MM.YYYY HH:MM', or ISO formats.
    """
    if pd.isna(dt_str) or not dt_str:
        return None
    
    dt_str = str(dt_str).strip()
    
    # Try different format patterns
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
            
    try:
        # Fallback to general pandas parsing if none of the above match
        return pd.to_datetime(dt_str)
    except:
        return None

def clean_sbb_chunk(df, target_stations):
    """
    Cleans a chunk of SBB raw actual data:
    - Filters for train transport (PRODUKT_ID or VERKEHRSMITTEL_TEXT == 'Zug' or other train indicators).
    - Filters for target stations by UIC code or name.
    - Parses date/times and calculates delays.
    
    Parameters:
    - df: Raw pandas DataFrame chunk
    - target_stations: List of dicts representing stations to keep (with uic_code and name)
    """
    # 1. Normalize column names (sometimes columns can be uppercase or lowercase)
    df.columns = [c.upper() for c in df.columns]
    
    # 2. Filter for trains only
    # SBB Produkt IDs: 'Zug' is trains, other categories include 'Bus', 'Schiff', 'Tram', etc.
    # We also look at VERKEHRSMITTEL_TEXT if PRODUKT_ID isn't present
    if "PRODUKT_ID" in df.columns:
        train_mask = df["PRODUKT_ID"].str.lower().isin(["zug", "train", "s", "ir", "ic", "re", "ec", "ice"])
        df = df[train_mask]
    elif "VERKEHRSMITTEL_TEXT" in df.columns:
        train_mask = df["VERKEHRSMITTEL_TEXT"].str.lower().isin(["zug", "s", "ir", "ic", "re", "ec", "ice"])
        df = df[train_mask]
        
    if df.empty:
        return pd.DataFrame()

    # 3. Filter for target stations
    # Match against BPUIC (Stop ID) or HALTESTELLEN_NAME
    target_uics = [s["uic_code"] for s in target_stations]
    target_names = [s["name"].lower() for s in target_stations]
    
    station_mask = pd.Series(False, index=df.index)
    if "BPUIC" in df.columns:
        # Stop IDs might be stored as string or int, normalize to string
        df["BPUIC"] = df["BPUIC"].astype(str).str.split('.').str[0]  # Remove decimal if float
        station_mask = station_mask | df["BPUIC"].isin(target_uics)
    if "HALTESTELLEN_NAME" in df.columns:
        station_mask = station_mask | df["HALTESTELLEN_NAME"].str.lower().isin(target_names)
        
    df = df[station_mask]
    if df.empty:
        return pd.DataFrame()

    cleaned_records = []
    
    for _, row in df.iterrows():
        # Parse operating day (BETRIEBSTAG)
        betriebstag_raw = row.get("BETRIEBSTAG")
        if pd.isna(betriebstag_raw):
            continue
        try:
            betriebstag = datetime.strptime(str(betriebstag_raw).strip(), "%d.%m.%Y").date()
        except ValueError:
            try:
                betriebstag = pd.to_datetime(betriebstag_raw).date()
            except:
                continue

        # Parse schedule and actual times
        sch_arr = parse_sbb_datetime(row.get("AN_SOLL"))
        act_arr = parse_sbb_datetime(row.get("AN_IST"))
        sch_dep = parse_sbb_datetime(row.get("AB_SOLL"))
        act_dep = parse_sbb_datetime(row.get("AB_IST"))
        
        # Calculate delays in minutes
        arr_delay = None
        if sch_arr and act_arr:
            arr_delay = round((act_arr - sch_arr).total_seconds() / 60.0, 1)
            # Clip negative delay values (early arrivals are 0 delay for prediction)
            arr_delay = max(0.0, arr_delay)
            
        dep_delay = None
        if sch_dep and act_dep:
            dep_delay = round((act_dep - sch_dep).total_seconds() / 60.0, 1)
            dep_delay = max(0.0, dep_delay)

        # Parse boolean flags
        faellt_aus = False
        if "FAELLT_AUS_TF" in df.columns:
            val = str(row.get("FAELLT_AUS_TF")).lower()
            faellt_aus = val in ["true", "t", "1", "yes"]
            
        zusatzfahrt = False
        if "ZUSATZFAHRT_TF" in df.columns:
            val = str(row.get("ZUSATZFAHRT_TF")).lower()
            zusatzfahrt = val in ["true", "t", "1", "yes"]

        # Map stop name/uic
        uic = str(row.get("BPUIC", "")).split('.')[0]
        # Find canonical station matching this row
        canonical_station = None
        for s in target_stations:
            if s["uic_code"] == uic or s["name"].lower() == str(row.get("HALTESTELLEN_NAME", "")).lower():
                canonical_station = s
                break
                
        if not canonical_station:
            continue
            
        cleaned_records.append({
            "betriebstag": betriebstag.strftime("%Y-%m-%d"),
            "fahrt_bezeichner": str(row.get("FAHRT_BEZEICHNER", "")),
            "produkt_id": "Zug",
            "linien_text": str(row.get("LINIEN_TEXT", row.get("LINIE_TEXT", ""))),
            "station_uic": canonical_station["uic_code"],
            "station_name": canonical_station["name"],
            "scheduled_arrival": sch_arr.strftime("%Y-%m-%d %H:%M:%S") if sch_arr else None,
            "actual_arrival": act_arr.strftime("%Y-%m-%d %H:%M:%S") if act_arr else None,
            "arrival_delay_min": arr_delay,
            "scheduled_departure": sch_dep.strftime("%Y-%m-%d %H:%M:%S") if sch_dep else None,
            "actual_departure": act_dep.strftime("%Y-%m-%d %H:%M:%S") if act_dep else None,
            "departure_delay_min": dep_delay,
            "faellt_aus": faellt_aus,
            "zusatzfahrt": zusatzfahrt
        })
        
    return pd.DataFrame(cleaned_records)
