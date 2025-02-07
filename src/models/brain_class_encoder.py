import torch
import torch.nn as nn

from .class_encoder import ClassEncoder
from .utils import Conv2D

"""
Input:
[B, C, E, T] (batch size, frequency bands (channels), electrodes, timesteps)

Output:
[B, C_OUT, L]
"""


class BrainClassEncoder(nn.Module):
    """
    Brain + class conditional encoder model. Takes brain (ECoG) recordings as input, and funnels them through a
    classification bottleneck, before projecting the classification results up to the size of the audio sequence.

    This essentially trains two models, a first classification model that learns to classify brain input, and a second
    class conditioning model that learns a class conditioning signal suitable for DiffWave.

    In practice, this second model may be pretrained together with DiffWave in the class-conditional pretraining
    setting, and frozen during fine-tuning.
    """

    def __init__(
        self,
        n_classes: int = 10,
        c_brain_in: int = 32,
        c_mid: int = 64,
        c_out: int = 128,
        **kwargs,
    ):
        super().__init__()

        # Different classifiers can be tested here by swapping out the class. Note that the required arguments
        # have to be appropriately specified in the model config file.
        self.brain_classifier = BrainClassifierV1(in_nodes=c_brain_in, n_classes=n_classes)
        # self.brain_classifier = BrainClassifierV3(in_channels=c_brain_in, n_classes=n_classes)

        # The second part is identical to the class encoder, so it will be reused.
        self.class_conditioner = ClassEncoder(n_classes=n_classes, c_mid=c_mid, c_out=c_out)

    def forward(self, x):
        x = self.brain_classifier(x)
        x = x.unsqueeze(1)  # [B, 55] -> [B, 1, 55]
        x = self.class_conditioner(x)
        return x


class BrainClassifierV1(nn.Module):
    def __init__(self, in_nodes: int, n_classes: int, **kwargs) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Flatten(),
            nn.Linear(in_nodes, in_nodes // 2),
            nn.ReLU(),
            nn.LayerNorm(in_nodes // 2),
            nn.Dropout(0.4),
            nn.Linear(in_nodes // 2, in_nodes // 4),
            nn.ReLU(),
            nn.LayerNorm(in_nodes // 4),
            nn.Dropout(0.3),
            nn.Linear(in_nodes // 4, n_classes),
            nn.Softmax(1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # [B, CxExT] -> [B, OUT_NODES]
        x = self.network(x)

        return x


class BrainClassifierV2(nn.Module):
    def __init__(self, n_classes: int = 10, **kwargs) -> None:
        super().__init__()
        self.network = nn.Sequential(
            # Temporal filtering
            Conv2D(2, 32, 3, (1, 2), 1),
            nn.ReLU(),
            nn.BatchNorm2d(32),
            nn.Dropout(0.1),
            Conv2D(32, 64, 3, (1, 2), 1),
            nn.ReLU(),
            nn.BatchNorm2d(64),
            nn.Dropout(0.1),
            Conv2D(64, 128, 3, (1, 2), 1),
            nn.ReLU(),
            nn.BatchNorm2d(128),
            nn.Dropout(0.1),
            # Spatio-temporal filtering
            Conv2D(128, 256, 3, (2, 3), 1),
            nn.ReLU(),
            nn.BatchNorm2d(256),
            nn.Dropout(0.1),
            Conv2D(256, 256, 3, (2, 3), 1),
            nn.ReLU(),
            nn.BatchNorm2d(256),
            nn.Dropout(0.1),
            nn.MaxPool2d(2, 2),
            # Flatten
            nn.Flatten(),
            # Classification
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.BatchNorm1d(128),
            nn.Dropout(0.5),
            nn.Linear(128, n_classes),
            nn.Softmax(1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.network(x)
        return x


class BrainClassifierV3(nn.Module):
    def __init__(self, in_channels: int, n_classes: int) -> None:
        super().__init__()

        self.network = nn.Sequential(
            Conv2D(in_channels, 64, kernel_size=(1, 3), stride=(1, 2), padding=(0, 1)),
            nn.ReLU(),
            # nn.MaxPool2d(kernel_size=(1,2), stride=(1,2)),
            Conv2D(64, 128, kernel_size=(2, 3), stride=(1, 1), padding=(0, 1)),
            nn.ReLU(),
            # nn.MaxPool2d(kernel_size=(1,2), stride=(1,2)),
            nn.Flatten(),
            nn.Linear(6400, 3200),
            nn.ReLU(),
            nn.Linear(3200, 1600),
            nn.ReLU(),
            nn.Linear(1600, n_classes),
            nn.Softmax(1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.network(x)
        return x
