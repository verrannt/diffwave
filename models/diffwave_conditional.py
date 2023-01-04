from typing import Any, Mapping, Optional

from omegaconf import DictConfig
import torch
import torch.nn as nn

from models.diffwave import DiffWave
from models.brain_class_encoder import BrainClassEncoder



class DiffWaveConditional(nn.Module):
    """
    Conditional wrapper model, to train and infer an encoder model and DiffWave together in a single model.
    """

    def __init__(self, encoder_class: nn.Module, encoder_cfg: DictConfig, decoder_cfg: DictConfig) -> None:
        super().__init__()
        
        self.encoder = encoder_class(**encoder_cfg)
        self.speech_generator = DiffWave(**decoder_cfg)

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
        checkpoint_dict: Mapping[str, Mapping[str, Any]],
    ):
        # The keys for the local conditioner will always be missing from a pretrained unconditional model, so we
        # set strict==False such that missing keys are ignored.
        inc_keys = self.speech_generator.load_state_dict(checkpoint_dict['model_state_dict'], strict=False)
        
        assert len(inc_keys.unexpected_keys) == 0, \
            f'Found unexpected keys: {inc_keys.unexpected_keys}'
        assert all(['local_conditioner' in k for k in inc_keys.missing_keys]), \
            f'Found missing keys for layers other than the local conditioner: {inc_keys.missing_keys}'

        # If using the BrainClassEncoder, need to also load the conditioner part of the network, as it was trained
        # together with the speech generator (i.e. the class-conditional setting). This will only load the 
        # class-conditioner part of the encoder, not the brain classifier part.
        if self.encoder.__class__.__name__ == 'BrainClassEncoder':
            inc_keys = self.encoder.load_state_dict(checkpoint_dict['conditioner_state_dict'], strict=False)
            
            assert len(inc_keys.unexpected_keys) == 0, \
                f'Found unexpected keys: {inc_keys.unexpected_keys}'
            assert all(['brain_classifier' in k for k in inc_keys.missing_keys]), \
                f'Found missing keys for layers other than the brain classifier: {inc_keys.missing_keys}'

    def encoder_state_dict(self):
        return self.encoder.state_dict()

    def generator_state_dict(self):
        return self.speech_generator.state_dict()

    def freeze_generator(self, freeze: bool = True):
        self.speech_generator.requires_grad_(not freeze)

        # If using the BrainClassEncoder, also freeze the conditioner part of the network, as it was trained
        # together with the speech generator (i.e. the class-conditional setting)
        if self.encoder.__class__.__name__ == 'BrainClassEncoder':
            self.encoder.embedding.requires_grad_(not freeze)
            self.encoder.projection.requires_grad_(not freeze)

    def unfreeze_generator(self):
        self.freeze_generator(False)