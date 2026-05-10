from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from functools import partial
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from dotenv import load_dotenv
from sklearn.preprocessing import LabelEncoder
from torch.utils.data import DataLoader

# apps/backend
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from app.ml.neumf_model import (
    NeuMF,
    NCFTrainDataset,
    NCFEvalDataset,
    build_user_positive_items,
    evaluate_model,
    get_item_vectors_from_neumf,
    ncf_collate_fn_weighted,
)


APP_ENV_FILE = os.getenv("APP_ENV_FILE", ".env.local")
ENV_FILE = BASE_DIR / APP_ENV_FILE
load_dotenv(ENV_FILE, override=True)


INPUT_PATH = (
    BASE_DIR
    / "artifacts"
    / "retraining"
    / "latest_training_interactions.csv"
)

MODEL_VERSION = os.getenv(
    "NEUMF_MODEL_VERSION",
    datetime.utcnow().strftime("neumf-local-%Y%m%d%H%M%S"),
)

OUTPUT_DIR = (
    BASE_DIR
    / "artifacts"
    / "models"
    / MODEL_VERSION
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FULL_MODEL_PATH = OUTPUT_DIR / "neumf_model.pt"
STATE_DICT_PATH = OUTPUT_DIR / "neumf_state_dict.pt"
USER_ENCODER_PATH = OUTPUT_DIR / "user_encoder.joblib"
ITEM_ENCODER_PATH = OUTPUT_DIR / "item_encoder.joblib"
ITEM_VECTORS_PATH = OUTPUT_DIR / "item_vectors.npy"
METADATA_PATH = OUTPUT_DIR / "training_metadata.json"


# Local training settings
GMF_EMB_SIZE = int(os.getenv("NEUMF_GMF_EMB_SIZE", "32"))
MLP_EMB_SIZE = int(os.getenv("NEUMF_MLP_EMB_SIZE", "32"))
MLP_LAYERS = [64, 32, 16, 8]

EPOCHS = int(os.getenv("NEUMF_EPOCHS", "3"))
BATCH_SIZE = int(os.getenv("NEUMF_BATCH_SIZE", "256"))
LEARNING_RATE = float(os.getenv("NEUMF_LR", "0.001"))

NUM_TRAIN_NEGATIVES = int(os.getenv("NEUMF_NUM_TRAIN_NEGATIVES", "4"))
NUM_EVAL_NEGATIVES = int(os.getenv("NEUMF_NUM_EVAL_NEGATIVES", "99"))

MIN_USER_POSITIVES = int(os.getenv("NEUMF_MIN_USER_POSITIVES", "5"))
MIN_ITEM_POSITIVES = int(os.getenv("NEUMF_MIN_ITEM_POSITIVES", "5"))

# For local testing. 0 means use all positive rows.
MAX_POSITIVE_ROWS = int(os.getenv("NEUMF_MAX_POSITIVE_ROWS", "200000"))

RANDOM_STATE = int(os.getenv("NEUMF_RANDOM_STATE", "42"))

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def event_time_to_sort_value(value) -> float:
    """
    Converts mixed event_time values into sortable numeric values.

    Supports:
    - MovieLens unix timestamps
    - PostgreSQL timestamp strings
    - missing values
    """

    if value is None or pd.isna(value):
        return 0.0

    # Try numeric timestamp first.
    try:
        numeric_value = float(value)

        # If milliseconds, convert to seconds.
        if numeric_value > 1e11:
            numeric_value = numeric_value / 1000.0

        return numeric_value

    except Exception:
        pass

    # Try datetime string.
    try:
        dt = pd.to_datetime(value, errors="coerce", utc=True)

        if pd.isna(dt):
            return 0.0

        return float(dt.timestamp())

    except Exception:
        return 0.0


def load_positive_interactions() -> pd.DataFrame:
    """
    Loads retraining interactions and keeps only positive rows.

    Your existing NeuMF training style uses positive interactions
    and generates negatives dynamically through negative sampling.
    """

    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Training file not found: {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH)

    required_cols = {
        "user_id",
        "movie_id",
        "label",
        "weight",
        "event_time",
    }

    missing = required_cols - set(df.columns)

    if missing:
        raise ValueError(f"Training file missing columns: {missing}")

    df = df.dropna(subset=["user_id", "movie_id", "label"]).copy()

    df["user_id"] = df["user_id"].astype(int)
    df["movie_id"] = df["movie_id"].astype(int)
    df["label"] = df["label"].astype(int)
    df["weight"] = df["weight"].astype(float)

    # Use positives only; negatives are sampled on the fly.
    df = df[df["label"] == 1].copy()

    if df.empty:
        raise RuntimeError("No positive interactions found for NeuMF training.")

    df["sort_time"] = df["event_time"].apply(event_time_to_sort_value)

    return df


def filter_sparse_users_and_items(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filters very sparse users/items so train/val/test split and
    negative sampling are stable.
    """

    filtered = df.copy()

    user_counts = filtered["user_id"].value_counts()
    active_users = user_counts[user_counts >= MIN_USER_POSITIVES].index
    filtered = filtered[filtered["user_id"].isin(active_users)].copy()

    item_counts = filtered["movie_id"].value_counts()
    popular_items = item_counts[item_counts >= MIN_ITEM_POSITIVES].index
    filtered = filtered[filtered["movie_id"].isin(popular_items)].copy()

    # After item filtering, some users may become too sparse.
    user_counts = filtered["user_id"].value_counts()
    active_users = user_counts[user_counts >= 3].index
    filtered = filtered[filtered["user_id"].isin(active_users)].copy()

    if filtered.empty:
        raise RuntimeError(
            "No data left after filtering sparse users/items. "
            "Lower NEUMF_MIN_USER_POSITIVES or NEUMF_MIN_ITEM_POSITIVES."
        )

    return filtered.reset_index(drop=True)


def limit_training_rows(df: pd.DataFrame) -> pd.DataFrame:
    if MAX_POSITIVE_ROWS and len(df) > MAX_POSITIVE_ROWS:
        return (
            df.sample(
                n=MAX_POSITIVE_ROWS,
                random_state=RANDOM_STATE,
            )
            .sort_values(["user_id", "sort_time"])
            .reset_index(drop=True)
        )

    return df.reset_index(drop=True)


def encode_user_and_item_ids(df: pd.DataFrame):
    user_encoder = LabelEncoder()
    item_encoder = LabelEncoder()

    encoded = df.copy()

    encoded["user_idx"] = user_encoder.fit_transform(encoded["user_id"])
    encoded["item_idx"] = item_encoder.fit_transform(encoded["movie_id"])

    return encoded, user_encoder, item_encoder


def split_train_val_test(df: pd.DataFrame):
    """
    Temporal split:
    - test = latest interaction per user
    - validation = second-latest interaction per user
    - train = remaining interactions
    """

    df = df.sort_values(["user_idx", "sort_time"]).reset_index(drop=True)

    test_df = df.groupby("user_idx").tail(1)
    remaining_df = df.drop(test_df.index)

    val_df = remaining_df.groupby("user_idx").tail(1)
    train_df = remaining_df.drop(val_df.index)

    if train_df.empty or val_df.empty or test_df.empty:
        raise RuntimeError(
            "Train/val/test split failed. Not enough interactions per user."
        )

    return (
        train_df.reset_index(drop=True),
        val_df.reset_index(drop=True),
        test_df.reset_index(drop=True),
    )


def train_neumf() -> dict:
    print("Loading positive interactions...")
    df = load_positive_interactions()

    print(f"Positive rows before filtering: {len(df):,}")

    df = filter_sparse_users_and_items(df)
    df = limit_training_rows(df)

    print(f"Positive rows after filtering/limit: {len(df):,}")

    print("Encoding users/items...")
    df, user_encoder, item_encoder = encode_user_and_item_ids(df)

    num_users = int(df["user_idx"].nunique())
    num_items = int(df["item_idx"].nunique())

    print(f"Users: {num_users:,}")
    print(f"Items: {num_items:,}")
    print(f"Interactions: {len(df):,}")

    print("Splitting train/val/test...")
    train_df, val_df, test_df = split_train_val_test(df)

    print(f"Train positives: {len(train_df):,}")
    print(f"Val positives: {len(val_df):,}")
    print(f"Test positives: {len(test_df):,}")

    train_user_pos_items = build_user_positive_items(train_df)
    all_user_pos_items = build_user_positive_items(df)

    train_dataset = NCFTrainDataset(train_df)

    train_rng = np.random.default_rng(RANDOM_STATE)

    collate_weighted = partial(
        ncf_collate_fn_weighted,
        num_items=num_items,
        user_pos_items=train_user_pos_items,
        num_negatives=NUM_TRAIN_NEGATIVES,
        rng=train_rng,
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=0,
        collate_fn=collate_weighted,
    )

    val_dataset = NCFEvalDataset(
        eval_df=val_df,
        num_items=num_items,
        user_pos_dict=all_user_pos_items,
        num_negatives=NUM_EVAL_NEGATIVES,
        rng=np.random.default_rng(RANDOM_STATE + 1),
        shuffle=True,
    )

    test_dataset = NCFEvalDataset(
        eval_df=test_df,
        num_items=num_items,
        user_pos_dict=all_user_pos_items,
        num_negatives=NUM_EVAL_NEGATIVES,
        rng=np.random.default_rng(RANDOM_STATE + 2),
        shuffle=True,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=1,
        shuffle=False,
        num_workers=0,
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=1,
        shuffle=False,
        num_workers=0,
    )

    print(f"Training device: {DEVICE}")

    model = NeuMF(
        num_users=num_users,
        num_items=num_items,
        gmf_emb_size=GMF_EMB_SIZE,
        mlp_emb_size=MLP_EMB_SIZE,
        mlp_layers=MLP_LAYERS,
    ).to(DEVICE)

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE,
    )

    criterion = nn.BCELoss(reduction="none")

    history: list[dict] = []

    for epoch in range(1, EPOCHS + 1):
        model.train()

        epoch_loss = 0.0
        batch_count = 0

        for user_batch, item_batch, label_batch, weight_batch in train_loader:
            user_batch = user_batch.to(DEVICE)
            item_batch = item_batch.to(DEVICE)
            label_batch = label_batch.to(DEVICE)
            weight_batch = weight_batch.to(DEVICE)

            optimizer.zero_grad()

            preds = model(user_batch, item_batch).view(-1)

            losses = criterion(preds, label_batch)
            weighted_loss = (losses * weight_batch).mean()

            weighted_loss.backward()
            optimizer.step()

            epoch_loss += float(weighted_loss.item())
            batch_count += 1

        avg_loss = epoch_loss / max(batch_count, 1)

        val_hr, val_ndcg = evaluate_model(
            model=model,
            data_loader=val_loader,
            device=DEVICE,
            k=10,
        )

        epoch_info = {
            "epoch": epoch,
            "weighted_loss": avg_loss,
            "val_hr_at_10": val_hr,
            "val_ndcg_at_10": val_ndcg,
        }

        history.append(epoch_info)

        print(
            f"Epoch {epoch}/{EPOCHS} "
            f"| loss={avg_loss:.4f} "
            f"| val_hr@10={val_hr:.4f} "
            f"| val_ndcg@10={val_ndcg:.4f}"
        )

    print("Running final test evaluation...")

    test_hr, test_ndcg = evaluate_model(
        model=model,
        data_loader=test_loader,
        device=DEVICE,
        k=10,
    )

    print(f"Test HR@10: {test_hr:.4f}")
    print(f"Test NDCG@10: {test_ndcg:.4f}")

    print("Extracting item vectors...")
    item_vectors = get_item_vectors_from_neumf(model)

    print("Saving artifacts...")

    torch.save(model, FULL_MODEL_PATH)
    torch.save(model.state_dict(), STATE_DICT_PATH)

    joblib.dump(user_encoder, USER_ENCODER_PATH)
    joblib.dump(item_encoder, ITEM_ENCODER_PATH)

    np.save(ITEM_VECTORS_PATH, item_vectors)

    metadata = {
        "model_version": MODEL_VERSION,
        "input_path": str(INPUT_PATH),
        "output_dir": str(OUTPUT_DIR),
        "full_model_path": str(FULL_MODEL_PATH),
        "state_dict_path": str(STATE_DICT_PATH),
        "user_encoder_path": str(USER_ENCODER_PATH),
        "item_encoder_path": str(ITEM_ENCODER_PATH),
        "item_vectors_path": str(ITEM_VECTORS_PATH),
        "num_users": num_users,
        "num_items": num_items,
        "positive_rows_used": int(len(df)),
        "train_positive_rows": int(len(train_df)),
        "val_positive_rows": int(len(val_df)),
        "test_positive_rows": int(len(test_df)),
        "gmf_emb_size": GMF_EMB_SIZE,
        "mlp_emb_size": MLP_EMB_SIZE,
        "mlp_layers": MLP_LAYERS,
        "epochs": EPOCHS,
        "batch_size": BATCH_SIZE,
        "learning_rate": LEARNING_RATE,
        "num_train_negatives": NUM_TRAIN_NEGATIVES,
        "num_eval_negatives": NUM_EVAL_NEGATIVES,
        "min_user_positives": MIN_USER_POSITIVES,
        "min_item_positives": MIN_ITEM_POSITIVES,
        "max_positive_rows": MAX_POSITIVE_ROWS,
        "device": str(DEVICE),
        "history": history,
        "test_hr_at_10": test_hr,
        "test_ndcg_at_10": test_ndcg,
    }

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(
            metadata,
            f,
            indent=2,
            default=str,
        )

    print("")
    print("NeuMF training completed.")
    print(f"Model version: {MODEL_VERSION}")
    print(f"Artifacts saved to: {OUTPUT_DIR}")

    return metadata


def main() -> None:
    train_neumf()


if __name__ == "__main__":
    main()