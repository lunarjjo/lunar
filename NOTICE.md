# NOTICE — third-party components bundled or used by lunar

lunar's own code is MIT (see LICENSE). It is built on the following
third-party components; their licenses and sources are preserved here.

## Kokoro-82M — the voice model

- Author: hexgrad
- Source: https://huggingface.co/hexgrad/Kokoro-82M
- License: Apache-2.0 (weights); voice style vectors are distributed under the
  terms stated on the model card (CC-BY family). Both are redistributed here
  only by reference — lunar downloads them at setup time and never commits
  them to this repository.
- Weights used: `kokoro-v1.0.onnx` / `kokoro-v1.0.int8.onnx` and
  `voices-v1.0.bin`.

## kokoro-onnx — ONNX export + runtime wrapper

- Author: thewh1teagle
- Source: https://github.com/thewh1teagle/kokoro-onnx (releases
  `model-files-v1.1`)
- License: MIT
- lunar downloads its model/voice files from this project's releases (with a
  Hugging Face mirror) and uses its Python API (`kokoro_onnx.Kokoro`,
  installed from PyPI) to drive inference.

## ONNX Runtime

- Source: https://github.com/microsoft/onnxruntime
- License: MIT
- Installed from PyPI (`onnxruntime`), CPU execution provider.

## espeak-ng + phonemizer — grapheme-to-phoneme conversion

- espeak-ng: https://github.com/espeak-ng/espeak-ng — GPLv3
- espeakng-loader (PyPI) bundles the espeak-ng shared library and data:
  https://github.com/rany2/espeakng-loader — MIT
- phonemizer: https://github.com/bootphon/phonemizer — GPLv3
- These arrive as dependencies of `kokoro-onnx`; they run locally and are
  never modified.

## FastAPI / Starlette / uvicorn / NumPy

- FastAPI: https://github.com/fastapi/fastapi — MIT
- Starlette: https://github.com/encode/starlette — BSD-3
- uvicorn: https://github.com/encode/uvicorn — BSD-3
- NumPy: https://numpy.org — BSD-3

## Attribution note

If you redistribute lunar with downloaded weights included (for example the
`lunar-modelpack` release asset), keep this NOTICE file with the archive and
credit Kokoro-82M by hexgrad and kokoro-onnx by thewh1teagle in anything you
publish with the audio you generate.
