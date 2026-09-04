"""Feedforward neural network: pure numpy, decoupled from the game engine.

Operates on plain arrays only -- never imports the game engine. Built
fresh from a genome's flat weight vector, used for forward passes, then
discarded; nothing here is ever adjusted by a gradient. Single hidden
layer only (MVP architecture; plan Sec3.4 reserves structural mutation,
i.e. multiple layers, for a later phase).
"""

from __future__ import annotations

import numpy as np


def weight_count(input_size: int, hidden_size: int, output_size: int) -> int:
    return (input_size * hidden_size + hidden_size) + (hidden_size * output_size + output_size)


class Network:
    def __init__(self, weights: np.ndarray, input_size: int, hidden_size: int, output_size: int) -> None:
        expected = weight_count(input_size, hidden_size, output_size)
        if weights.shape != (expected,):
            raise ValueError(f"expected {expected} weights, got shape {weights.shape}")

        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size

        i = 0
        self.w1 = weights[i:i + input_size * hidden_size].reshape(input_size, hidden_size)
        i += input_size * hidden_size
        self.b1 = weights[i:i + hidden_size]
        i += hidden_size
        self.w2 = weights[i:i + hidden_size * output_size].reshape(hidden_size, output_size)
        i += hidden_size * output_size
        self.b2 = weights[i:i + output_size]

    def forward(self, x: np.ndarray) -> np.ndarray:
        hidden = np.tanh(x @ self.w1 + self.b1)
        return hidden @ self.w2 + self.b2

    def flatten(self) -> np.ndarray:
        return np.concatenate([self.w1.flatten(), self.b1, self.w2.flatten(), self.b2])
