# Copyright (c) 2023, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Classification convert etlt model to TRT engine."""

import logging
import os
import tempfile

from nvidia_tao_deploy.utils.decoding import decode_model

from nvidia_tao_deploy.cv.classification_tf1.engine_builder import ClassificationEngineBuilder
from nvidia_tao_deploy.cv.common.decorators import monitor_status
from nvidia_tao_deploy.cv.common.hydra.hydra_runner import hydra_runner
from nvidia_tao_deploy.cv.classification_pyt.hydra_config.default_config import ExperimentConfig
from nvidia_tao_deploy.engine.builder import NV_TENSORRT_MAJOR, NV_TENSORRT_MINOR, NV_TENSORRT_PATCH

logging.basicConfig(format='%(asctime)s [TAO Toolkit] [%(levelname)s] %(name)s %(lineno)d: %(message)s',
                    level="INFO")
logger = logging.getLogger(__name__)

spec_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@hydra_runner(
    config_path=os.path.join(spec_root, "specs"),
    config_name="gen_trt_engine", schema=ExperimentConfig
)
@monitor_status(name='classification_pyt', mode='gen_trt_engine')
def main(cfg: ExperimentConfig) -> None:
    """Classification TRT convert."""
    # decrypt EFF or etlt
    tmp_onnx_file, file_format = decode_model(cfg.gen_trt_engine.onnx_file)

    data_type = cfg.gen_trt_engine.tensorrt.data_type.lower()

    # TODO: TRT8.6.1 improves INT8 perf
    if data_type == 'int8':
        raise NotImplementedError("INT8 calibration for PyTorch classification models is not yet supported")

    if cfg.gen_trt_engine.trt_engine is not None:
        if cfg.gen_trt_engine.trt_engine is None:
            engine_handle, temp_engine_path = tempfile.mkstemp()
            os.close(engine_handle)
            output_engine_path = temp_engine_path
        else:
            output_engine_path = cfg.gen_trt_engine.trt_engine

        min_batch_size = cfg.gen_trt_engine.tensorrt.min_batch_size
        opt_batch_size = cfg.gen_trt_engine.tensorrt.opt_batch_size
        max_batch_size = cfg.gen_trt_engine.tensorrt.max_batch_size

        # TODO: Remove this when we upgrade to DLFW 23.04+
        trt_version_number = NV_TENSORRT_MAJOR * 1000 + NV_TENSORRT_MINOR * 100 + NV_TENSORRT_PATCH
        if data_type == "fp16" and trt_version_number < 8600:
            logger.warning("[WARNING]: LayerNorm has overflow issue in FP16 upto TensorRT version 8.5 "
                           "which can lead to accuracy drop compared to FP32.\n"
                           "[WARNING]: Please re-export ONNX using opset 17 and use TensorRT version 8.6.\n")

        builder = ClassificationEngineBuilder(verbose=cfg.gen_trt_engine.verbose,
                                              workspace=cfg.gen_trt_engine.tensorrt.workspace_size,
                                              min_batch_size=min_batch_size,
                                              opt_batch_size=opt_batch_size,
                                              max_batch_size=max_batch_size,
                                              is_qat=False,
                                              data_format="channels_first",
                                              preprocess_mode="torch")
        builder.create_network(tmp_onnx_file, file_format)
        builder.create_engine(
            output_engine_path,
            cfg.gen_trt_engine.tensorrt.data_type)

    if cfg.gen_trt_engine.results_dir:
        results_dir = cfg.gen_trt_engine.results_dir
    else:
        results_dir = os.path.join(cfg.results_dir, "gen_trt_engine")
    os.makedirs(results_dir, exist_ok=True)

    print("Export finished successfully.")


if __name__ == '__main__':
    main()
