# src/data_processing/earthquake_features.py

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import logging

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

config_file = project_root / "config" / "config.yaml"
assert config_file.exists(), f"Config file missing at {config_file}"

from src.utils.helpers import setup_logging, load_config

# features engineering
class EarthquakeFeatureEngineering:
    """
    Feature engineering + imbalance-safe target construction
    for earthquake early-warning prediction.
    """

    def __init__(self, config=None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

    def create_temporal_features(self, df):
        print("\nCreating temporal features...")

        df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
        df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)

        df["day_sin"] = np.sin(2 * np.pi * df["day"] / 31)
        df["day_cos"] = np.cos(2 * np.pi * df["day"] / 31)

        if "hour" in df.columns:
            df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
            df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)

        df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
        df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)

        return df

    def create_seismic_activity_features(self, df):
        print("\nCreating seismic activity features...")

        df = df.sort_values("time").reset_index(drop=True)

        windows = {
            "6h": 6,
            "12h": 12,
            "1d": 24,
            "3d": 72,
            "7d": 168,
        }

        energy = 10 ** (1.5 * df["mag"] + 4.8)

        for label, w in windows.items():
            roll = df["mag"].rolling(w, min_periods=1)

            df[f"eq_count_{label}"] = roll.count()
            df[f"eq_avg_mag_{label}"] = roll.mean()
            df[f"eq_max_mag_{label}"] = roll.max()
            df[f"eq_std_mag_{label}"] = roll.std()
            df[f"eq_energy_{label}"] = energy.rolling(w, min_periods=1).sum()

        # acceleration ratios (precursor signals)
        df["count_accel_6h_1d"] = df["eq_count_6h"] / (df["eq_count_1d"] + 1)
        df["count_accel_1d_3d"] = df["eq_count_1d"] / (df["eq_count_3d"] + 1)

        df["energy_accel_6h_1d"] = df["eq_energy_6h"] / (df["eq_energy_1d"] + 1)
        df["energy_accel_1d_3d"] = df["eq_energy_1d"] / (df["eq_energy_3d"] + 1)

        df["max_mag_jump_6h"] = df["eq_max_mag_6h"] - df["eq_avg_mag_1d"]
        df["max_mag_jump_1d"] = df["eq_max_mag_1d"] - df["eq_avg_mag_3d"]

        return df

    def create_spatial_features(self, df):
        print("\nCreating spatial features...")

        san_andreas_lat = 36.0
        san_andreas_lon = -120.0

        df["dist_san_andreas_km"] = (
            np.sqrt(
                (df["latitude"] - san_andreas_lat) ** 2 +
                (df["longitude"] - san_andreas_lon) ** 2
            ) * 111
        )

        df["dist_coast_km"] = np.abs(df["longitude"] + 124.0) * 85
        return df

    def create_lag_features(self, df, lags=(1, 2, 3, 7, 14, 30)):
        print("\nCreating lag features...")

        df = df.sort_values("time").reset_index(drop=True)

        for lag in lags:
            df[f"mag_lag_{lag}h"] = df["mag"].shift(lag)
            df[f"depth_lag_{lag}h"] = df["depth"].shift(lag)

        df["time_since_last_h"] = (
            df["time"].diff().dt.total_seconds() / 3600
        )

        return df
    
    def create_interaction_features(self, df):
        print("\nCreating interaction features...")

        df["mag_depth_interaction"] = df["mag"] * df["depth"]
        df["mag_squared"] = df["mag"] ** 2
        df["depth_squared"] = df["depth"] ** 2
        df["energy_proxy"] = 10 ** (1.5 * df["mag"] + 4.8)

        return df

    def create_target_variable(
        self,
        df,
        prediction_window_hours=168,
        main_threshold=5.0,
        near_threshold=4.5,
        max_negative_ratio=5,
        min_pos_per_event=24,
    ):
        print("\nCreating target variable...")

        df = df.sort_values("time").reset_index(drop=True)

        # identify earthquake events
        df["is_event"] = (
            (df["mag"] >= main_threshold) |
            (df["mag"] >= near_threshold)
        ).astype(int)

        event_indices = df.index[df["is_event"] == 1].to_numpy()
        target = np.zeros(len(df), dtype=int)

        # label precursor windows
        for idx in event_indices:
            start = max(0, idx - prediction_window_hours)
            target[start:idx] = 1

            if idx - start < min_pos_per_event:
                extra = max(0, idx - min_pos_per_event)
                target[extra:idx] = 1

        df["target"] = target

        # hard negative mining
        positives = df[df["target"] == 1]
        negatives = df[df["target"] == 0]

        activity_score = (
            df["eq_count_1d"].fillna(0) +
            df["eq_energy_1d"].fillna(0)
        )

        negatives = negatives.loc[
            activity_score.loc[negatives.index] >
            activity_score.quantile(0.60)
        ]

        max_negatives = max_negative_ratio * len(positives)
        if len(negatives) > max_negatives:
            negatives = negatives.sample(
                n=max_negatives,
                random_state=42
            )

        df = (
            pd.concat([positives, negatives])
            .sort_values("time")
            .reset_index(drop=True)
        )

        print(
            f"Target positive rate: {df['target'].mean():.2%} "
            f"({df['target'].sum():,} / {len(df):,})"
        )

        return df

def engineer_earthquake_features():
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    setup_logging(str(log_dir / "earthquake_feature_engineering.log"))

    config = load_config(str(config_file))

    input_file = project_root / "data" / "processed" / "earthquake_cleaned.csv"
    if not input_file.exists():
        raise FileNotFoundError("Run earthquake_cleaner.py first")

    df = pd.read_csv(input_file)

    if not pd.api.types.is_datetime64_any_dtype(df["time"]):
        df["time"] = pd.to_datetime(df["time"], errors="coerce")
        df = df.dropna(subset=["time"]).reset_index(drop=True)

    engineer = EarthquakeFeatureEngineering(config)

    df = engineer.create_temporal_features(df)
    df = engineer.create_seismic_activity_features(df)
    df = engineer.create_spatial_features(df)
    df = engineer.create_lag_features(df)
    df = engineer.create_interaction_features(df)

    df = engineer.create_target_variable(
        df,
        prediction_window_hours=168,
        main_threshold=config["earthquake"]["significant_magnitude"],
        near_threshold=config["earthquake"].get(
            "near_significant_magnitude", 4.5
        ),
        max_negative_ratio=5,
    )

    df = df.dropna().reset_index(drop=True)

    output_dir = project_root / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "earthquake_features.csv"
    df.to_csv(output_file, index=False)

    print(f"\nFinal dataset: {df.shape}")
    print(df["target"].value_counts())
    print(f"Saved to {output_file}")

    return df


if __name__ == "__main__":
    engineer_earthquake_features()
