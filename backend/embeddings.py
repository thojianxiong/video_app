from __future__ import annotations

from collections import OrderedDict
from typing import Sequence

import numpy as np
import open_clip
import torch
from PIL import Image


class OpenCLIPEmbedder:
    def __init__(
        self,
        model_name: str = "ViT-L-14",
        pretrained: str = "openai",
        cache_dir: str | None = None,
        text_cache_size: int = 512,
        device_preference: str = "auto",
    ) -> None:
        self.model_name = str(model_name)
        self.pretrained = str(pretrained)
        self.device_preference = str(device_preference or "auto").strip().lower()
        self.device = self._resolve_device(self.device_preference)
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            model_name=self.model_name,
            pretrained=self.pretrained,
            device=self.device,
            cache_dir=cache_dir,
        )
        self.tokenizer = open_clip.get_tokenizer(self.model_name)
        self.model.eval()
        self.text_cache_size = max(1, text_cache_size)
        self._text_cache: OrderedDict[str, np.ndarray] = OrderedDict()

        with torch.no_grad():
            probe = self.tokenizer(["dimension probe"]).to(self.device)
            encoded = self.model.encode_text(probe)
        self.embedding_dim = int(encoded.shape[-1])

    @staticmethod
    def _resolve_device(device_preference: str) -> str:
        normalized = str(device_preference or "auto").strip().lower()
        if normalized in {"", "auto", "default"}:
            return "cuda" if torch.cuda.is_available() else "cpu"
        if normalized in {"cpu"}:
            return "cpu"
        if normalized in {"cuda", "gpu"}:
            if not torch.cuda.is_available():
                raise ValueError(
                    "OPENCLIP_DEVICE is set to 'cuda' but CUDA is not available. "
                    "Set OPENCLIP_DEVICE=auto or OPENCLIP_DEVICE=cpu."
                )
            return "cuda"
        raise ValueError(
            "Invalid OPENCLIP_DEVICE value. Allowed values: auto, cuda, cpu."
        )

    def _normalize(self, features: torch.Tensor) -> torch.Tensor:
        return features / features.norm(dim=-1, keepdim=True).clamp_min(1e-12)

    def _cache_put(self, text: str, embedding: np.ndarray) -> None:
        self._text_cache[text] = embedding
        self._text_cache.move_to_end(text)
        while len(self._text_cache) > self.text_cache_size:
            self._text_cache.popitem(last=False)

    def encode_text(self, text: str) -> np.ndarray:
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("Text query cannot be empty")

        cached = self._text_cache.get(normalized_text)
        if cached is not None:
            self._text_cache.move_to_end(normalized_text)
            return cached.copy()

        with torch.no_grad():
            tokens = self.tokenizer([normalized_text]).to(self.device)
            if self.device == "cuda":
                with torch.cuda.amp.autocast(dtype=torch.float16):
                    text_features = self.model.encode_text(tokens)
            else:
                text_features = self.model.encode_text(tokens)

            text_features = self._normalize(text_features)
            embedding = (
                text_features[0]
                .detach()
                .float()
                .cpu()
                .numpy()
                .astype(np.float32)
            )

        self._cache_put(normalized_text, embedding)
        return embedding.copy()

    def encode_images(
        self,
        images: Sequence[Image.Image],
        batch_size: int = 32,
    ) -> np.ndarray:
        if not images:
            return np.empty((0, self.embedding_dim), dtype=np.float32)

        batch_size = max(1, int(batch_size))
        collected = []

        with torch.no_grad():
            for start_idx in range(0, len(images), batch_size):
                chunk = images[start_idx : start_idx + batch_size]
                image_tensor = torch.stack(
                    [self.preprocess(image.convert("RGB")) for image in chunk],
                    dim=0,
                ).to(self.device)

                if self.device == "cuda":
                    with torch.cuda.amp.autocast(dtype=torch.float16):
                        image_features = self.model.encode_image(image_tensor)
                else:
                    image_features = self.model.encode_image(image_tensor)

                image_features = self._normalize(image_features)
                collected.append(
                    image_features.detach().float().cpu().numpy().astype(np.float32)
                )

        return np.vstack(collected)
