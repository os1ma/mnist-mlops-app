import os
import uuid
from datetime import datetime
from io import BytesIO

import numpy as np
import onnxruntime
from fastapi import FastAPI, File, UploadFile
from PIL import Image
from scipy.special import softmax

from app.dao.image_dao import ImageDao
from app.dao.model_dao import ModelDao

MODEL_FILE = '/model.onnx'


def log_info(message: str) -> None:
    now = datetime.now()
    print(f"[{now}] {message}")


def get_model_tag() -> str:
    return os.environ['MODEL_TAG']


app = FastAPI()


@app.get('/api/health')
async def health():
    return {'health': 'ok'}


@app.get('/api/models/current')
async def current_model():
    tag = get_model_tag()
    return {'tag': tag}

# TODO @app.get('/api/predictions')


@app.post('/api/predictions')
async def predict(image: UploadFile = File(...)):
    id = uuid.uuid4()
    log_info(f"predict called. id = {id}")

    # preprocess image file

    filename = image.filename
    log_info(f"filename = {filename}")
    data = await image.read()
    pil_image = Image.open(BytesIO(data))
    os.makedirs(f"data/{id}")
    original_image_filename = f"data/{id}/original.png"
    pil_image.save(original_image_filename)
    # 28 * 28 に変換
    resized = pil_image.resize((28, 28))
    resized_image_filename = f"data/{id}/resized.png"
    resized.save(resized_image_filename)
    arr = np.array(resized)
    log_info(f"arr.shpae = {arr.shape}")
    # 軸の変換
    transposed = arr.transpose()[3:]
    log_info(
        f"transposed.shape = {transposed.shape}, transposed = {transposed}, max = {np.amax(transposed)}")
    # 型を変換
    typed = transposed.astype('float32')
    # 0 ~ 1 に正規化
    standardized = typed / 255
    log_info(
        f"standardized.shape = {standardized.shape}, standardized = {standardized}")

    # predict
    onnx_session = onnxruntime.InferenceSession(MODEL_FILE)
    input_name = onnx_session.get_inputs()[0].name
    output = onnx_session.run(None, {input_name: standardized})
    log_info(f"output = {output}")

    result = softmax(output[0][0]).tolist()
    log_info(f"result = {result}")

    # モデルが DB に保存されていなければ保存する
    tag = get_model_tag()
    m = ModelDao().find_by_tag(tag)
    log_info(f"model = {m}")
    if m == None:
        ModelDao().insert(tag)

    # 画像を保存
    ImageDao().insert(original_image_filename, resized_image_filename)

    return {'result': result}
