import os

if os.environ.get('MODE') == 'dev':
    reload = True

bind = '0.0.0.0:5000'
workers = 1

worker_class = 'uvicorn.workers.UvicornWorker'

# https://docs.gunicorn.org/en/stable/faq.html#how-do-i-avoid-gunicorn-excessively-blocking-in-os-fchmod
worker_tmp_dir = '/dev/shm'
