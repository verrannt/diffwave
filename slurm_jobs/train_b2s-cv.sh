#!/bin/bash
#SBATCH --job-name="train-b2s-uv"
#SBATCH --nodes=1
#SBATCH --ntasks=72
#SBATCH --gpus=4
#SBATCH --time=03:30:00
#SBATCH --partition=gpu

echo
echo TRAIN B2S-Uv
echo 
echo $(date +"%D %T")
echo

# Load modules from registry
echo [$(date +"%T")] Loading modules
module purge
module load 2021
module load cuDNN/8.2.1.32-CUDA-11.3.1
module load Python/3.9.5-GCCcore-10.3.0

# Activate python virtual environment
echo [$(date +"%T")] Activating virtual environment
source venvs/diffwave/bin/activate

# Copy codebase
echo [$(date +"%T")] Copying codebase
cp -r $HOME/brain2speech-diffusion $TMPDIR/brain2speech-diffusion

# Change directory
echo [$(date +"%T")] Navigating to $TMPDIR/brain2speech-diffusion
cd $TMPDIR/brain2speech-diffusion

# Run computation
echo [$(date +"%T")] Executing train script
python src/train.py \
    train.name=B2S-Cv_v9 \
    experiment=B2S-Cv \
    generate.conditional_signal=data/HP1_ECoG_conditional/sub-002/dag2.npy \
    generate.conditional_type=brain \
    model.freeze_generator=true \
    model.pretrained_generator=exp/SG-C_v3/checkpoint/180.pkl \
    train.n_epochs=8 \
    train.epochs_per_ckpt=1 \
    train.iters_per_logging=100 \
    train.batch_size_per_gpu=12 \
    generate.n_samples=12 \
    wandb.mode=online \
    # wandb.id=<id> \
    # +wandb.resume=true \

# Retrieve outputs
echo [$(date +"%T")] Retrieving outputs
cp -r exp/* $HOME/brain2speech-diffusion/exp

# Deactivate virtual environment
echo [$(date +"%T")] Deactivating virtual environment
deactivate

echo [$(date +"%T")] Done
