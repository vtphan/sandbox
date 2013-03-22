import multiprocessing

bind = "127.0.0.1:8000"
worker_class = "gevent"

workers = multiprocessing.cpu_count() * 2 + 1
