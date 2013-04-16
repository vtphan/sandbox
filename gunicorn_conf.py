# import multiprocessing

#bind = "127.0.0.1:8000"
bind = "0.0.0.0:8000"
worker_class = "gevent"
t = 99999
workers = 4 #multiprocessing.cpu_count() * 2 + 1
timeout = 86400
debuy = True
