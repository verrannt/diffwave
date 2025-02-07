from abc import ABC, abstractmethod
import os
from pathlib import Path
import re
from typing import List, Optional
import sys

sys.path.append("..")
from utils.generic import get_word_from_filepath

import numpy as np
import torch
from torch import Tensor


class ClassConditionalLoader:
    """
    Load class conditional input vector for a given word. Returns a callable object that upon being
    called with a word (or filepath containing a the word in the filename), returns a one-hot
    encoded class vector. The indexes of the encoding are specified in a words file or list of
    words provided at initialization.

    Params:
    ---
    `words_file`: path to the file containing the words to index. Has to be comma-separated,
        without blank spaces.
    `words_list`: alternative to providing a file on disk, a list of the words can be given
        directly.
    """

    def __init__(self, words_file: str = None, words_list: Optional[List[str]] = None) -> None:
        if words_list is not None:
            words = words_list
        elif words_file is not None:
            with open(words_file, "r") as file:
                words = file.read().split(",")
        else:
            raise ValueError("One of words_file or words_list must not be None")
        self.word_tokens = {words[i]: i for i in range(len(words))}
        self.num_classes = len(words)

    def __call__(self, audio_file_path: str, **kwargs) -> Tensor:
        word = get_word_from_filepath(audio_file_path)
        try:
            idx = self.word_tokens[word]
        except KeyError:
            raise ValueError(f"Unrecognized word: {word}")
        out = torch.LongTensor([idx])
        out = torch.nn.functional.one_hot(out, self.num_classes)
        out = out.type(torch.float32)
        return out

    def batch_call(self, audio_file_list: List[str], one_hot: bool = True) -> Tensor:
        """
        For faster processing of multiple files, call this function with a list of file paths.
        Will return a batched tensor of one-hot encoded class labels if `one_hot==True`, else just
        a tensor of the indexes.
        """
        words = [get_word_from_filepath(fp) for fp in audio_file_list]
        try:
            idxs = [self.word_tokens[word] for word in words]
        except KeyError:
            raise ValueError(f"Could not recognize one of {words}")
        if one_hot:
            out = torch.LongTensor(idxs)
            out = torch.nn.functional.one_hot(out, self.num_classes)
            out = out.type(torch.float32)
        else:
            out = torch.FloatTensor(idxs)
        return out


class ECOGLoader(ABC):
    """
    Abstract class for implementing an ECoG loader. Subclasses must implement the `retrieve_file`
    function which returns an ECoG file when given an audio file as input.
    """

    def __call__(self, audio_file_path: str, **kwargs) -> Tensor:
        # Retrieving a matching ECoG file must be handled by the inheriting classes
        ecog_file = self.retrieve_file(audio_file_path, **kwargs)
        ecog = self.process_ecog(ecog_file)
        return ecog

    @staticmethod
    def process_ecog(ecog_file: str) -> Tensor:
        """
        Load an ECoG array as PyTorch `Tensor` from disk.

        Params:
        ---
        `ecog_file`: Path to the stored ECoG file as numpy array on disk.

        Returns:
        ---
        `ecog`: The loaded ECoG array as PyTorch `Tensor`.
        """
        # Load from path
        ecog = torch.from_numpy(np.load(ecog_file)).float()
        return ecog

    @abstractmethod
    def retrieve_file(self, audio_file_path: str, **kwargs) -> str:
        pass


class ECOGRandomLoader(ECOGLoader):
    """
    Given a filepath pointing to an audio file for a given word, randomly
    load an ECoG file corresponding to the word.
    """

    def __init__(
        self,
        path: str,
        splits_path: str,
        seed: int,
    ) -> None:
        self.rng = np.random.default_rng(seed)

        with open(Path(splits_path) / "train.csv", "r") as f_t, open(
            Path(splits_path) / "val.csv", "r"
        ) as f_v:
            self.train_words = [word.split(".")[0] for word in f_t.read().split(",")]
            self.val_words = [word.split(".")[0] for word in f_v.read().split(",")]

        train_files = [
            file
            for file in os.listdir(path)
            if file.endswith(".npy")
            and get_word_from_filepath(file, uses_numbering=False) in self.train_words
        ]

        val_files = [
            file
            for file in os.listdir(path)
            if file.endswith(".npy")
            and get_word_from_filepath(file, uses_numbering=False) in self.val_words
        ]

        self.files = {"train": train_files, "val": val_files}

        self.path = Path(path)

    def retrieve_file(self, audio_file_path: str, set: str) -> str:
        # Isolate word from given file path. Note that there is no need to remove numbers as the
        # dataset supposed to provide the audio files has no numbering in the top-level filename.
        # This will break in case of file numbering.
        word = get_word_from_filepath(audio_file_path, uses_numbering=False)

        # Find all ECoG files for this word
        fitting_files = [
            file
            for file in self.files[set]
            if get_word_from_filepath(file, uses_augmentation=False) == word
        ]

        if len(fitting_files) == 0:
            raise ValueError(f"No ECoG files found for {audio_file_path}")

        # Randomly select one of the ECoG files
        file = self.rng.choice(fitting_files)

        # Prepend path
        file = self.path / file

        return file


class ECOGExactLoader(ECOGLoader):
    """
    Given a filepath pointing to an audio file for a given word, load the ECoG
    file corresponding to exactly that audio recording.
    """

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def retrieve_file(self, audio_file_path: str, **kwargs) -> str:
        # Isolate word from given file path
        # Note that we must not remove numbering, since the number tells us which ECoG file to load
        # (e.g. 'goed7.wav' corresponds to 'goed7.npy')
        word = get_word_from_filepath(
            audio_file_path, uses_numbering=False, uses_augmentation=False
        )

        # Select the ECoG file for this word
        file = self.path / f"{word}.npy"

        return file
