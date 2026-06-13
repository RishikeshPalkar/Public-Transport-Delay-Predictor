"""
Phase 2: XGBoost Model Training & Evaluation
=============================================
Trains XGBoost Regressors for departure and arrival delay prediction
using the features produced by features.py.

Strategy:
  - Time-Series Split: trains on the first ~83% of days (5 months), validates on the last ~17% (1 month).
  - Trains two separate models: departure delay and arrival delay.
  - Evaluates with MAE, RMSE, and R² score.
  - Saves trained models and feature importance plots to models/ directory.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for saving plots
import matplotlib.pyplot as plt
from datetime import datetime

from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Allow imports from sibling packages
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import build_feature_dataset


# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")

XGBOOST_PARAMS = {
    "n_estimators": 500,
    "max_depth": 6,
    "learning_rate": 0.08,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "random_state": 42,
    "n_jobs": -1,
    "early_stopping_rounds": 20,
}


def time_series_split(df, train_ratio=0.83):
    """
    Splits the dataframe chronologically.
    train_ratio=0.83 means ~5 months train, ~1 month test for a 6-month dataset.
    """
    df = df.sort_values("betriebstag").reset_index(drop=True)
    split_idx = int(len(df) * train_ratio)

    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()

    train_dates = pd.to_datetime(train_df["betriebstag"])
    test_dates = pd.to_datetime(test_df["betriebstag"])

    print(f"\n-- Time-Series Split --")
    print(f"   Train: {len(train_df):,} rows  ({train_dates.min().date()} -> {train_dates.max().date()})")
    print(f"   Test:  {len(test_df):,} rows  ({test_dates.min().date()} -> {test_dates.max().date()})")

    return train_df, test_df


def train_and_evaluate(train_df, test_df, feature_cols, target_col, model_name):
    """
    Trains an XGBoost regressor on the training set and evaluates on the test set.
    Returns the trained model and evaluation metrics.
    """
    # Filter to rows that have valid target values
    train_valid = train_df[train_df[target_col].notna()].copy()
    test_valid = test_df[test_df[target_col].notna()].copy()

    if train_valid.empty or test_valid.empty:
        print(f"  [WARN] Skipping {model_name}: insufficient data (train={len(train_valid)}, test={len(test_valid)})")
        return None, None

    X_train = train_valid[feature_cols].values
    y_train = train_valid[target_col].values
    X_test = test_valid[feature_cols].values
    y_test = test_valid[target_col].values

    print(f"\n{'=' * 60}")
    print(f"  Training: {model_name}")
    print(f"  Target: {target_col}")
    print(f"  Train samples: {len(X_train):,} | Test samples: {len(X_test):,}")
    print(f"  Features: {len(feature_cols)}")
    print(f"{'=' * 60}")

    # Initialize and train the model
    model = XGBRegressor(**XGBOOST_PARAMS)
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=50  # Print progress every 50 rounds
    )

    # Predictions
    y_pred = model.predict(X_test)

    # Clip negative predictions to 0 (delays can't be negative)
    y_pred = np.clip(y_pred, 0, None)

    # Evaluation metrics
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    metrics = {"MAE": round(mae, 3), "RMSE": round(rmse, 3), "R2": round(r2, 4)}

    print(f"\n  [OK] {model_name} Evaluation Results:")
    print(f"     MAE  (Mean Absolute Error):  {mae:.3f} minutes")
    print(f"     RMSE (Root Mean Sq. Error):  {rmse:.3f} minutes")
    print(f"     R2   (Coefficient of Det.):  {r2:.4f}")

    return model, metrics


def save_model(model, model_name, feature_cols, metrics):
    """Saves the trained XGBoost model and metadata to the models/ directory."""
    os.makedirs(MODELS_DIR, exist_ok=True)

    # Save model in native XGBoost JSON format
    model_path = os.path.join(MODELS_DIR, f"{model_name}.json")
    model.save_model(model_path)
    print(f"  [SAVED] Model saved: {model_path}")

    # Save metadata (feature names, metrics, training date)
    meta = {
        "model_name": model_name,
        "trained_at": datetime.now().isoformat(),
        "n_features": len(feature_cols),
        "feature_names": feature_cols,
        "xgboost_params": XGBOOST_PARAMS,
        "metrics": metrics,
    }
    meta_path = os.path.join(MODELS_DIR, f"{model_name}_metadata.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"  [META] Metadata saved: {meta_path}")


def plot_feature_importance(model, feature_cols, model_name, top_n=15):
    """Generates and saves a feature importance bar chart."""
    os.makedirs(MODELS_DIR, exist_ok=True)

    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1][:top_n]

    top_features = [feature_cols[i] for i in indices]
    top_importances = importances[indices]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(range(len(top_features)), top_importances[::-1], color="#4C72B0", edgecolor="#2F4F7F")
    ax.set_yticks(range(len(top_features)))
    ax.set_yticklabels(top_features[::-1], fontsize=10)
    ax.set_xlabel("Feature Importance (Gain)", fontsize=12)
    ax.set_title(f"Top {top_n} Feature Importances — {model_name}", fontsize=14, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()

    plot_path = os.path.join(MODELS_DIR, f"{model_name}_feature_importance.png")
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    print(f"  [PLOT] Feature importance plot saved: {plot_path}")


def main():
    print("=" * 60)
    print("  Phase 2: XGBoost Model Training Pipeline")
    print("=" * 60)

    # Step 1: Build feature dataset
    df, feature_cols = build_feature_dataset()
    if df is None:
        print("Aborting: no feature data available.")
        return

    # Step 2: Time-series split
    train_df, test_df = time_series_split(df, train_ratio=0.83)

    # Step 3: Train departure delay model
    dep_model, dep_metrics = train_and_evaluate(
        train_df, test_df, feature_cols,
        target_col="departure_delay_min",
        model_name="departure_delay_xgb"
    )

    if dep_model:
        save_model(dep_model, "departure_delay_xgb", feature_cols, dep_metrics)
        plot_feature_importance(dep_model, feature_cols, "departure_delay_xgb")

    # Step 4: Train arrival delay model
    arr_model, arr_metrics = train_and_evaluate(
        train_df, test_df, feature_cols,
        target_col="arrival_delay_min",
        model_name="arrival_delay_xgb"
    )

    if arr_model:
        save_model(arr_model, "arrival_delay_xgb", feature_cols, arr_metrics)
        plot_feature_importance(arr_model, feature_cols, "arrival_delay_xgb")

    # Summary
    print("\n" + "=" * 60)
    print("  Phase 2 Training Complete!")
    print("=" * 60)
    if dep_metrics:
        print(f"  Departure Delay Model -> MAE: {dep_metrics['MAE']}  RMSE: {dep_metrics['RMSE']}  R2: {dep_metrics['R2']}")
    if arr_metrics:
        print(f"  Arrival   Delay Model -> MAE: {arr_metrics['MAE']}  RMSE: {arr_metrics['RMSE']}  R2: {arr_metrics['R2']}")
    print(f"  Models saved in: {os.path.abspath(MODELS_DIR)}")


if __name__ == "__main__":
    main()
