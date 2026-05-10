from __future__ import annotations

from collections import defaultdict
from typing import Iterable

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset


class GMF(nn.Module):
    def __init__(self, num_users: int, num_items: int, emb_size: int = 32):
        super().__init__()

        self.user_emb = nn.Embedding(num_users, emb_size)
        self.item_emb = nn.Embedding(num_items, emb_size)
        self.output = nn.Linear(emb_size, 1)

        self._init_weights()

    def _init_weights(self) -> None:
        nn.init.normal_(self.user_emb.weight, std=0.01)
        nn.init.normal_(self.item_emb.weight, std=0.01)
        nn.init.normal_(self.output.weight, std=0.01)
        nn.init.zeros_(self.output.bias)

    def forward(
        self,
        user_idx: torch.Tensor,
        item_idx: torch.Tensor,
    ) -> torch.Tensor:
        user_vec = self.user_emb(user_idx)
        item_vec = self.item_emb(item_idx)

        interaction = user_vec * item_vec
        logit = self.output(interaction)

        return torch.sigmoid(logit)


class MLP(nn.Module):
    def __init__(
        self,
        num_users: int,
        num_items: int,
        emb_size: int = 32,
        layers: list[int] | None = None,
    ):
        super().__init__()

        if layers is None:
            layers = [64, 32, 16, 8]

        self.user_emb = nn.Embedding(num_users, emb_size)
        self.item_emb = nn.Embedding(num_items, emb_size)

        mlp_layers: list[nn.Module] = []
        input_size = emb_size * 2

        for layer_size in layers:
            mlp_layers.append(nn.Linear(input_size, layer_size))
            mlp_layers.append(nn.ReLU())
            input_size = layer_size

        self.mlp = nn.Sequential(*mlp_layers)
        self.output = nn.Linear(layers[-1], 1)

        self._init_weights()

    def _init_weights(self) -> None:
        nn.init.normal_(self.user_emb.weight, std=0.01)
        nn.init.normal_(self.item_emb.weight, std=0.01)

        for layer in self.mlp:
            if isinstance(layer, nn.Linear):
                nn.init.normal_(layer.weight, std=0.01)
                nn.init.zeros_(layer.bias)

        nn.init.normal_(self.output.weight, std=0.01)
        nn.init.zeros_(self.output.bias)

    def forward(
        self,
        user_idx: torch.Tensor,
        item_idx: torch.Tensor,
    ) -> torch.Tensor:
        user_vec = self.user_emb(user_idx)
        item_vec = self.item_emb(item_idx)

        x = torch.cat([user_vec, item_vec], dim=-1)
        hidden = self.mlp(x)
        logit = self.output(hidden)

        return torch.sigmoid(logit)


class NeuMF(nn.Module):
    def __init__(
        self,
        num_users: int,
        num_items: int,
        gmf_emb_size: int = 32,
        mlp_emb_size: int = 32,
        mlp_layers: list[int] | None = None,
    ):
        super().__init__()

        if mlp_layers is None:
            mlp_layers = [64, 32, 16, 8]

        self.num_users = num_users
        self.num_items = num_items
        self.gmf_emb_size = gmf_emb_size
        self.mlp_emb_size = mlp_emb_size
        self.mlp_layers_config = mlp_layers

        self.gmf_user_emb = nn.Embedding(num_users, gmf_emb_size)
        self.gmf_item_emb = nn.Embedding(num_items, gmf_emb_size)

        self.mlp_user_emb = nn.Embedding(num_users, mlp_emb_size)
        self.mlp_item_emb = nn.Embedding(num_items, mlp_emb_size)

        mlp: list[nn.Module] = []
        input_size = mlp_emb_size * 2

        for layer_size in mlp_layers:
            mlp.append(nn.Linear(input_size, layer_size))
            mlp.append(nn.ReLU())
            input_size = layer_size

        self.mlp_layers = nn.Sequential(*mlp)

        fusion_size = gmf_emb_size + mlp_layers[-1]
        self.final = nn.Linear(fusion_size, 1)

        self._init_weights()

    def _init_weights(self) -> None:
        nn.init.normal_(self.gmf_user_emb.weight, std=0.01)
        nn.init.normal_(self.gmf_item_emb.weight, std=0.01)
        nn.init.normal_(self.mlp_user_emb.weight, std=0.01)
        nn.init.normal_(self.mlp_item_emb.weight, std=0.01)

        for layer in self.mlp_layers:
            if isinstance(layer, nn.Linear):
                nn.init.normal_(layer.weight, std=0.01)
                nn.init.zeros_(layer.bias)

        nn.init.normal_(self.final.weight, std=0.01)
        nn.init.zeros_(self.final.bias)

    def forward(
        self,
        user_idx: torch.Tensor,
        item_idx: torch.Tensor,
    ) -> torch.Tensor:
        # GMF path
        gmf_user = self.gmf_user_emb(user_idx)
        gmf_item = self.gmf_item_emb(item_idx)
        gmf_out = gmf_user * gmf_item

        # MLP path
        mlp_user = self.mlp_user_emb(user_idx)
        mlp_item = self.mlp_item_emb(item_idx)
        mlp_input = torch.cat([mlp_user, mlp_item], dim=-1)
        mlp_out = self.mlp_layers(mlp_input)

        # Fusion
        vector = torch.cat([gmf_out, mlp_out], dim=-1)
        logit = self.final(vector)

        return torch.sigmoid(logit)


class NCFTrainDataset(Dataset):
    """
    Holds positive interactions only.

    Negative examples are generated dynamically in the collate function.
    """

    def __init__(self, train_df):
        self.users = train_df["user_idx"].to_numpy(dtype=np.int64)
        self.items = train_df["item_idx"].to_numpy(dtype=np.int64)
        self.weights = train_df["weight"].to_numpy(dtype=np.float32)

    def __len__(self) -> int:
        return len(self.users)

    def __getitem__(self, idx: int):
        return (
            int(self.users[idx]),
            int(self.items[idx]),
            float(self.weights[idx]),
        )


def ncf_collate_fn_weighted(
    batch,
    num_items: int,
    user_pos_items: dict[int, set[int]],
    num_negatives: int = 4,
    rng: np.random.Generator | None = None,
):
    """
    Converts a batch of positive interactions into positive + sampled negative rows.

    Returns:
        user_tensor
        item_tensor
        label_tensor
        weight_tensor
    """

    if rng is None:
        rng = np.random.default_rng()

    user_list: list[int] = []
    item_list: list[int] = []
    label_list: list[float] = []
    weight_list: list[float] = []

    for user_idx, positive_item_idx, positive_weight in batch:
        positive_items_for_user = user_pos_items.get(user_idx, set())

        # Positive example
        user_list.append(user_idx)
        item_list.append(positive_item_idx)
        label_list.append(1.0)
        weight_list.append(positive_weight)

        # Negative examples
        neg_count = 0

        while neg_count < num_negatives:
            sampled_item = int(rng.integers(0, num_items))

            if sampled_item not in positive_items_for_user:
                user_list.append(user_idx)
                item_list.append(sampled_item)
                label_list.append(0.0)
                weight_list.append(1.0)
                neg_count += 1

    user_tensor = torch.tensor(user_list, dtype=torch.long)
    item_tensor = torch.tensor(item_list, dtype=torch.long)
    label_tensor = torch.tensor(label_list, dtype=torch.float32)
    weight_tensor = torch.tensor(weight_list, dtype=torch.float32)

    return user_tensor, item_tensor, label_tensor, weight_tensor


class NCFEvalDataset(Dataset):
    """
    Evaluation dataset.

    For each user-positive item pair, samples N negatives and returns
    a candidate set containing one positive item and multiple negatives.
    """

    def __init__(
        self,
        eval_df,
        num_items: int,
        user_pos_dict: dict[int, set[int]],
        num_negatives: int = 99,
        rng: np.random.Generator | None = None,
        shuffle: bool = True,
    ):
        self.users = eval_df["user_idx"].to_numpy(dtype=np.int64)
        self.pos_items = eval_df["item_idx"].to_numpy(dtype=np.int64)

        self.num_items = num_items
        self.user_pos_dict = user_pos_dict
        self.num_negatives = num_negatives
        self.shuffle = shuffle
        self.rng = rng or np.random.default_rng()

    def __len__(self) -> int:
        return len(self.users)

    def __getitem__(self, idx: int):
        user_idx = int(self.users[idx])
        positive_item_idx = int(self.pos_items[idx])

        positive_items_for_user = self.user_pos_dict.get(user_idx, set())

        negatives: list[int] = []

        while len(negatives) < self.num_negatives:
            sampled_item = int(self.rng.integers(0, self.num_items))

            if sampled_item not in positive_items_for_user:
                negatives.append(sampled_item)

        items = [positive_item_idx] + negatives
        labels = [1.0] + [0.0] * self.num_negatives

        if self.shuffle:
            permutation = self.rng.permutation(len(items))
            items = [items[i] for i in permutation]
            labels = [labels[i] for i in permutation]

        user_tensor = torch.tensor(user_idx, dtype=torch.long)
        item_tensor = torch.tensor(items, dtype=torch.long)
        label_tensor = torch.tensor(labels, dtype=torch.float32)

        return user_tensor, item_tensor, label_tensor


def build_user_positive_items(df) -> dict[int, set[int]]:
    """
    Builds user_idx -> set(item_idx) from a dataframe.
    """

    result: dict[int, set[int]] = defaultdict(set)

    users = df["user_idx"].to_numpy()
    items = df["item_idx"].to_numpy()

    for user_idx, item_idx in zip(users, items):
        result[int(user_idx)].add(int(item_idx))

    return result


def evaluate_model(
    model: nn.Module,
    data_loader,
    device: torch.device,
    k: int = 10,
) -> tuple[float, float]:
    """
    Returns:
        HR@K, NDCG@K
    """

    model.eval()

    hits: list[float] = []
    ndcgs: list[float] = []

    with torch.no_grad():
        for user_batch, item_batch, label_batch in data_loader:
            user_batch = user_batch.to(device)
            item_batch = item_batch.to(device)
            label_batch = label_batch.to(device)

            # user_batch shape: [1]
            # item_batch shape: [1, 100]
            user_expanded = user_batch.repeat(1, item_batch.size(1))

            users_flat = user_expanded.view(-1)
            items_flat = item_batch.view(-1)

            scores = model(users_flat, items_flat).view(1, -1)

            scores_np = scores.squeeze(0).detach().cpu().numpy()
            labels_np = label_batch.squeeze(0).detach().cpu().numpy()

            ranked_indices = np.argsort(-scores_np)

            positive_indices = np.where(labels_np == 1)[0]

            if len(positive_indices) == 0:
                continue

            positive_index = positive_indices[0]
            rank = np.where(ranked_indices == positive_index)[0][0] + 1

            hit = 1.0 if rank <= k else 0.0
            hits.append(hit)

            if rank <= k:
                ndcg = 1.0 / np.log2(rank + 1)
            else:
                ndcg = 0.0

            ndcgs.append(ndcg)

    if not hits:
        return 0.0, 0.0

    return float(np.mean(hits)), float(np.mean(ndcgs))


def get_item_vectors_from_neumf(model: nn.Module) -> np.ndarray:
    """
    Extracts CF-learned item vectors from trained NeuMF.

    Uses:
    - GMF item embeddings
    - MLP item embeddings

    Returns normalized matrix:
        shape = [num_items, gmf_dim + mlp_dim]
    """

    model.eval()

    with torch.no_grad():
        gmf_item = model.gmf_item_emb.weight.detach().cpu().numpy()
        mlp_item = model.mlp_item_emb.weight.detach().cpu().numpy()

    item_vectors = np.concatenate([gmf_item, mlp_item], axis=1)

    norms = np.linalg.norm(item_vectors, axis=1, keepdims=True)
    item_vectors_norm = item_vectors / np.clip(norms, 1e-8, None)

    return item_vectors_norm


def compute_item_similarities(
    item_idx: int,
    item_vectors: np.ndarray,
) -> np.ndarray:
    """
    Computes cosine similarity between one item and all items.

    Assumes item_vectors are already L2-normalized.
    """

    query_vector = item_vectors[item_idx]
    similarities = item_vectors @ query_vector

    return similarities


def movieid_to_itemidx(movie_id: int, item_encoder) -> int:
    try:
        return int(item_encoder.transform([movie_id])[0])
    except Exception as exc:
        raise ValueError(
            f"movie_id {movie_id} not found in item encoder."
        ) from exc


def itemidx_to_movieid(item_idx: int, item_encoder) -> int:
    return int(item_encoder.inverse_transform([item_idx])[0])


def similar_movies_cf(
    movie_id: int,
    item_vectors: np.ndarray,
    item_encoder,
    top_k: int = 10,
    exclude_self: bool = True,
) -> list[dict]:
    item_idx = movieid_to_itemidx(movie_id, item_encoder)

    similarities = compute_item_similarities(
        item_idx=item_idx,
        item_vectors=item_vectors,
    )

    if exclude_self:
        similarities[item_idx] = -1.0

    top_indices = np.argsort(-similarities)[:top_k]

    results: list[dict] = []

    for idx in top_indices:
        raw_movie_id = itemidx_to_movieid(
            item_idx=int(idx),
            item_encoder=item_encoder,
        )

        results.append(
            {
                "movie_id": raw_movie_id,
                "similarity": float(similarities[idx]),
            }
        )

    return results