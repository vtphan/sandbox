import multiprocessing

bind = "127.0.0.1:8000"
worker_class = "gevent"
workers = 4 #multiprocessing.cpu_count() * 2 + 1
timeout = 86400
