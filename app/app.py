import random
from threading import Lock
from typing import Any, Dict

from environs import Env
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi_socketio import SocketManager
from loguru import logger

from .loading_messages import loading_messages
from .utils.route_finder import dynamically_register_routes

Env().read_env()  # load .env file
app = FastAPI()
socket_manager = SocketManager(app=app)

dynamically_register_routes(app)

templates = Jinja2Templates(directory="templates")
thread = None
thread_lock = Lock()


async def background_thread():
    """Example of how to send server generated events to clients."""
    while True:
        await app.sio.sleep(10)
        logger.info('emitting background generated message')
        await app.sio.emit('stream_response', random.choice(loading_messages), namespace='/socketio')


@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse('index.html', {"request": request})


@app.get('/loading_message')
async def loading_message():
    logger.info('loading_message')
    return {"message": random.choice(loading_messages)}


@app.sio.on('my_message', namespace='/socketio')
async def handle_message(sid: str, message: str):
    logger.info('handle_message')
    await app.sio.emit('my_response', f'Your message "{message}" is stupid!', namespace='/socketio')


@app.sio.on('stream', namespace='/socketio')
async def handle_stream(sid: str):
    logger.info('handle_stream')
    await app.sio.emit('stream_response', random.choice(loading_messages), broadcast=True, namespace='/socketio')


@app.sio.on('connect', namespace='/socketio')
async def test_connect(sid: str, environ: Dict[str, Any]):
    global thread
    with thread_lock:
        if thread is None:
            thread = app.sio.start_background_task(background_thread)
    await app.sio.emit('my_response', {'data': 'Connected', 'count': 0})

logger.info('App Initialized')
