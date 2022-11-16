from typing import Any, Mapping, Optional

import torch
import torch.nn as nn

from models.brain_encoder import BrainEncoder
from models.diffwave import DiffWave



class DiffBrain(nn.Module): #CoBraWave, CoBraDiff, DiffCoBra, BrainConditionalSpeechGen
    def __init__(self, encoder_params, decoder_params) -> None:
        super().__init__()
            
        self.encoder = BrainEncoder(**encoder_params)
        self.speech_generator = DiffWave(**decoder_params)

    def forward(self, x, conditional_input):
        
        # Global projection of conditional input, before it's fed into generator
        conditional_input = self.encoder(conditional_input)

        # Generator takes both diffusion input x_t and global conditional input
        x = self.speech_generator(x, conditional_input)

        return x

    def load_state_dict(
        self, 
        generator_state_dict: Mapping[str, Any], 
        encoder_state_dict: Optional[Mapping[str, Any]] = None,
        strict: bool = True
    ):
        
        self.speech_generator.load_state_dict(generator_state_dict, strict)
        
        if encoder_state_dict is not None:
            self.encoder.load_state_dict(encoder_state_dict, strict)

    def load_pretrained_generator(
        self,
        state_dict: Mapping[str, Any],
    ):
        # The keys for the local conditioner will always be missing from a pretrained unconditional model, so we
        # set strict==False such that missing keys are ignored.
        inc_keys = self.speech_generator.load_state_dict(state_dict, strict=False)
        
        assert len(inc_keys.unexpected_keys) == 0, \
            f'Found unexpected keys: {inc_keys.unexpected_keys}'
        assert all(['local_conditioner' in k for k in inc_keys.missing_keys]), \
            f'Found missing keys for layers other than the local conditioner: {inc_keys.missing_keys}'

    def encoder_state_dict(self):
        return self.encoder.state_dict()

    def generator_state_dict(self):
        return self.speech_generator.state_dict()