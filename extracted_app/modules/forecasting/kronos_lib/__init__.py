"""
modules/forecasting/kronos_lib

Vendored copy of the model-definition code from shiyu-coder/Kronos
("Kronos: A Foundation Model for the Language of Financial Markets"),
MIT licensed — see LICENSE in this folder.

Only the pure model/tokenizer/predictor classes are vendored here (no
finetuning or webui code). Pretrained weights are NOT bundled with the app;
they are streamed from the Hugging Face Hub the first time a model is
loaded (see kronos_engine.load_kronos_predictor), the same as upstream.

Upstream repo: https://github.com/shiyu-coder/Kronos
Paper: https://arxiv.org/abs/2508.02739
"""

from modules.forecasting.kronos_lib.kronos_model import (
    KronosTokenizer,
    Kronos,
    KronosPredictor,
)

__all__ = ["KronosTokenizer", "Kronos", "KronosPredictor"]
